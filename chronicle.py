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
LOG_FILE = "tautulli_sonarr.log"
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
    """Ensures the next 5 consecutive episodes are monitored and triggers search."""
    try:
        log_info(f"Fetching episodes for Series ID: {series_id}...")
        episodes_response = requests.get(
            f"{SONARR_API_URL}/episode",
            headers={"X-Api-Key": SONARR_API_KEY},
            params={"seriesId": series_id},
            timeout=10
        )
        episodes_response.raise_for_status()
        episodes = episodes_response.json()

        # Sort episodes by season and episode number
        sorted_episodes = sorted(episodes, key=lambda e: (e['seasonNumber'], e['episodeNumber']))

        episodes_to_update = []
        total_checked = 0  # Tracks how many episodes we've processed (up to 5)
        next_episode = current_episode + 1

        while total_checked < EPISODES_TO_MONITOR:
            # Find the episode corresponding to the next one
            episode_found = next(
                (
                    ep for ep in sorted_episodes
                    if ep['seasonNumber'] == season_number and ep['episodeNumber'] == next_episode
                ),
                None
            )

            if not episode_found:
                # If no episode is found in the current season, stop checking
                break

            # If the episode isn't monitored or downloaded, add it to the update list
            if not episode_found['monitored'] and not episode_found['hasFile']:
                episodes_to_update.append(episode_found)

            # Move to the next episode
            next_episode += 1
            total_checked += 1

        if episodes_to_update:
            # Update the selected episodes to be monitored
            for ep in episodes_to_update:
                payload = {"monitored": True}
                try:
                    update_response = requests.put(
                        f"{SONARR_API_URL}/episode/{ep['id']}",
                        headers={"X-Api-Key": SONARR_API_KEY},
                        json=payload,
                        timeout=10
                    )
                    update_response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    log_error(f"Failed to enable monitoring for Episode {ep['seasonNumber']}x{ep['episodeNumber']}: {e}")

            # Log the episodes marked for monitoring
            episodes_str = ', '.join(
                f"{ep['seasonNumber']}x{ep['episodeNumber']}" for ep in episodes_to_update
            )
            log_info(f"Season {season_number}: Episodes {episodes_str} marked for monitoring.")

            # Trigger search for the monitored episodes
            search_payload = {
                "name": "EpisodeSearch",
                "episodeIds": [ep['id'] for ep in episodes_to_update],
            }
            try:
                search_response = requests.post(
                    f"{SONARR_API_URL}/command",
                    headers={"X-Api-Key": SONARR_API_KEY},
                    json=search_payload,
                    timeout=10
                )
                search_response.raise_for_status()
                log_info("Search triggered for monitored episodes.")
            except requests.exceptions.RequestException as e:
                log_error(f"Error triggering search for episodes: {e}")
        else:
            log_info("No new episodes to monitor.")
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
