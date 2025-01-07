import requests
import time
import logging

# Configuration
TAUTULLI_API_URL = "http://<TAUTULLI_SERVER_IP>:<TAUTULLI_PORT>/api/v2"
TAUTULLI_API_KEY = "<YOUR_TAUTULLI_API_KEY>"
SONARR_API_URL = "http://<SONARR_SERVER_IP>:<SONARR_PORT>/api/v3"
SONARR_API_KEY = "<YOUR_SONARR_API_KEY>"

# Customizable settings
MONITOR_ENTIRE_SEASON = False  # Monitor the entire season if True
EPISODES_TO_MONITOR = 5  # Number of episodes to monitor after the current one
WATCHED_PERCENTAGE = 70  # Trigger when watched percentage exceeds this

# Logging configuration
LOG_FILE = "chronicle.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_info(message):
    logging.info(message)
    print(message)

def log_error(message):
    logging.error(message)
    print(message)

def get_current_activity():
    """Fetches current activity from Tautulli."""
    try:
        params = {'apikey': TAUTULLI_API_KEY, 'cmd': 'get_activity'}
        response = requests.get(TAUTULLI_API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error(f"Error fetching activity from Tautulli: {e}")
        return None

def get_download_queue():
    """Fetches the Sonarr download queue."""
    try:
        response = requests.get(f"{SONARR_API_URL}/queue", headers={"X-Api-Key": SONARR_API_KEY}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error(f"Error fetching Sonarr download queue: {e}")
        return []

def monitor_next_episodes(series_id, current_episode, season_number, download_queue):
    """Enables monitoring and triggers search for the next episodes."""
    try:
        episodes_response = requests.get(
            f"{SONARR_API_URL}/episode",
            headers={"X-Api-Key": SONARR_API_KEY},
            params={"seriesId": series_id},
            timeout=10
        )
        episodes_response.raise_for_status()
        episodes = episodes_response.json()

        episodes_to_update = [
            ep for ep in episodes
            if ep['seasonNumber'] == season_number
            and current_episode < ep['episodeNumber'] <= current_episode + EPISODES_TO_MONITOR
            and not ep['hasFile']
            and ep['id'] not in [item['episodeId'] for item in download_queue if 'episodeId' in item]
        ]

        for ep in episodes_to_update:
            payload = {"monitored": True}
            update_response = requests.put(
                f"{SONARR_API_URL}/episode/{ep['id']}",
                headers={"X-Api-Key": SONARR_API_KEY},
                json=payload
            )
            update_response.raise_for_status()

        if episodes_to_update:
            log_info(f"Monitoring enabled for {len(episodes_to_update)} episodes starting from Episode {current_episode + 1}.")
            search_payload = {"name": "EpisodeSearch", "seriesId": series_id, "episodeIds": [ep['id'] for ep in episodes_to_update]}
            search_response = requests.post(
                f"{SONARR_API_URL}/command",
                headers={"X-Api-Key": SONARR_API_KEY},
                json=search_payload
            )
            search_response.raise_for_status()
            log_info("Search triggered for monitored episodes.")
        else:
            log_info("No new episodes to monitor or search.")
    except requests.exceptions.RequestException as e:
        log_error(f"Error during monitor or search process: {e}")

def main():
    while True:
        log_info("Checking current activity...")
        activity = get_current_activity()
        if not activity or 'response' not in activity or 'data' not in activity['response'] or not activity['response']['data']['sessions']:
            log_info("No active sessions found. Sleeping for 60 seconds...")
            time.sleep(60)
            continue

        sessions = activity['response']['data']['sessions']
        log_info(f"Active sessions found: {len(sessions)}")
        download_queue = get_download_queue()

        for session in sessions:
            if session.get('media_type') != 'episode':
                continue

            progress = int(session.get('progress_percent', 0))
            if progress < WATCHED_PERCENTAGE:
                continue

            title = session.get('grandparent_title', "Unknown Title")
            season_number = int(session.get('parent_media_index', 0))
            current_episode = int(session.get('media_index', 0))
            tvdb_id = session.get('grandparent_rating_key')

            log_info(f"Processing: {title}, Season {season_number}, Episode {current_episode} - {progress}% watched.")

            try:
                series_response = requests.get(
                    f"{SONARR_API_URL}/series/lookup",
                    headers={"X-Api-Key": SONARR_API_KEY},
                    params={"term": f"tvdb:{tvdb_id}"}
                )
                series_response.raise_for_status()
                series_data = series_response.json()

                matching_series = next((s for s in series_data if s.get('tvdbId') == int(tvdb_id)), None)

                if not matching_series:
                    log_info(f"No exact match for TVDB ID: {tvdb_id}. Trying to lookup by title: {title}...")
                    title_response = requests.get(
                        f"{SONARR_API_URL}/series/lookup",
                        headers={"X-Api-Key": SONARR_API_KEY},
                        params={"term": title}
                    )
                    title_response.raise_for_status()
                    title_results = title_response.json()

                    matching_series = next((s for s in title_results if s.get('title', '').lower() == title.lower()), None)

                if matching_series:
                    series_id = matching_series['id']
                    monitor_next_episodes(series_id, current_episode, season_number, download_queue)
                else:
                    log_info(f"Series not found in Sonarr for TVDB ID {tvdb_id} or title {title}. Skipping...")
            except requests.exceptions.RequestException as e:
                log_error(f"Error processing session: {e}")

        log_info("Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main()
