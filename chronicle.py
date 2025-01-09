import requests
import time
import logging

# Configuration
TAUTULLI_API_URL = "http://your-tautulli-url/api/v2"  # Replace with your Tautulli URL
TAUTULLI_API_KEY = "your-tautulli-api-key"  # Replace with your Tautulli API key
SONARR_API_URL = "http://your-sonarr-url/api/v3"  # Replace with your Sonarr URL
SONARR_API_KEY = "your-sonarr-api-key"  # Replace with your Sonarr API key

# Customizable settings
MONITOR_ENTIRE_SEASON = False  # Set True to monitor the entire current season
MONITOR_NEXT_SEASON = False  # Set True to monitor the rest of the current and following season
MONITOR_ENTIRE_SERIES = False  # Set True to monitor the entire series (including future episodes)
EPISODES_TO_MONITOR = 5  # Number of episodes to monitor after the current one
WATCHED_PERCENTAGE = 70  # Trigger when watched percentage exceeds this

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# State tracking
session_state = {}

def log_info(message):
    """Log an info message."""
    logging.info(message)

def log_error(message):
    """Log an error message."""
    logging.error(message)

def get_current_activity():
    """Fetch current activity from Tautulli."""
    try:
        params = {'apikey': TAUTULLI_API_KEY, 'cmd': 'get_activity'}
        response = requests.get(TAUTULLI_API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error(f"Error fetching activity from Tautulli: {e}")
        return None

def monitor_next_episodes(series_id, current_episode, season_number, session_key):
    """Monitor episodes based on configuration with precedence."""
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

        # Retrieve session-specific state
        monitored_episodes = session_state.get(session_key, set())
        episodes_to_update = []

        # Determine episodes to monitor based on settings precedence
        if MONITOR_ENTIRE_SERIES:
            log_info("Monitoring the entire series.")
            episodes_to_update = [
                ep for ep in sorted_episodes
                if ep['id'] not in monitored_episodes and not ep['hasFile'] and not ep['monitored']
            ]
        elif MONITOR_NEXT_SEASON:
            log_info("Monitoring the rest of the current and next season.")
            current_season_episodes = [
                ep for ep in sorted_episodes
                if ep['seasonNumber'] == season_number and ep['episodeNumber'] > current_episode
            ]
            next_season_episodes = [
                ep for ep in sorted_episodes if ep['seasonNumber'] == season_number + 1
            ]
            episodes_to_update = [
                ep for ep in current_season_episodes + next_season_episodes
                if ep['id'] not in monitored_episodes and not ep['hasFile'] and not ep['monitored']
            ]
        elif MONITOR_ENTIRE_SEASON:
            log_info("Monitoring the rest of the current season.")
            episodes_to_update = [
                ep for ep in sorted_episodes
                if ep['seasonNumber'] == season_number and ep['episodeNumber'] > current_episode and
                ep['id'] not in monitored_episodes and not ep['hasFile'] and not ep['monitored']
            ]
        else:
            log_info("Monitoring the next configured number of episodes.")
            for ep in sorted_episodes:
                if len(episodes_to_update) >= EPISODES_TO_MONITOR:
                    break
                if (
                    ep['id'] not in monitored_episodes and not ep['hasFile'] and not ep['monitored'] and
                    ((ep['seasonNumber'] == season_number and ep['episodeNumber'] > current_episode) or
                     ep['seasonNumber'] > season_number)
                ):
                    episodes_to_update.append(ep)
                    monitored_episodes.add(ep['id'])

        # Update session state
        session_state[session_key] = monitored_episodes

        if episodes_to_update:
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

            episodes_str = ', '.join(f"{ep['seasonNumber']}x{ep['episodeNumber']}" for ep in episodes_to_update)
            log_info(f"Episodes marked for monitoring: {episodes_str}")

        else:
            log_info("No new episodes to monitor.")
    except requests.exceptions.RequestException as e:
        log_error(f"Error during monitor or search process: {e}")

def main():
    """Main function to continuously monitor and process episodes."""
    while True:
        try:
            log_info("Checking current activity...")
            activity = get_current_activity()
            if not activity or 'response' not in activity or 'data' not in activity['response'] or not activity['response']['data']['sessions']:
                log_info("No active sessions found. Sleeping for 60 seconds...")
                time.sleep(60)
                continue

            sessions = activity['response']['data']['sessions']
            log_info(f"Active sessions found: {len(sessions)}")

            for session in sessions:
                if session.get('media_type') != 'episode':
                    continue

                progress = int(session.get('progress_percent', 0))
                if progress < WATCHED_PERCENTAGE:
                    continue

                title = session.get('grandparent_title', "Unknown Title")
                season_number = int(session.get('parent_media_index', 0))
                current_episode = int(session.get('media_index', 0))
                session_key = f"{title}_S{season_number}"

                log_info(f"Processing: {title}, Season {season_number}, Episode {current_episode} - {progress}% watched.")

                monitor_next_episodes(session.get('grandparent_id'), current_episode, season_number, session_key)

            log_info("Sleeping for 60 seconds...")
            time.sleep(60)
        except Exception as e:
            log_error(f"Unhandled exception: {e}")

if __name__ == "__main__":
    log_info("Script started.")
    main()
