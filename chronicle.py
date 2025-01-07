import requests
import json
import time

# Configuration
TAUTULLI_API_URL = "http://<TAUTULLI_SERVER_IP>:<TAUTULLI_PORT>/api/v2"
TAUTULLI_API_KEY = "<YOUR_TAUTULLI_API_KEY>"
SONARR_API_URL = "http://<SONARR_SERVER_IP>:<SONARR_PORT>/api/v3"
SONARR_API_KEY = "<YOUR_SONARR_API_KEY>"

# Function to get current activity from Tautulli
def get_current_activity():
    params = {
        'apikey': TAUTULLI_API_KEY,
        'cmd': 'get_activity'
    }
    print("Fetching current activity from Tautulli...")
    response = requests.get(TAUTULLI_API_URL, params=params)
    print(f"Tautulli Response Code: {response.status_code}")
    if response.status_code != 200:
        print("Failed to fetch current activity.")
        print(response.text)
        return None
    return response.json()

# Function to get the Sonarr download queue
def get_download_queue():
    print("Fetching download queue from Sonarr...")
    response = requests.get(f"{SONARR_API_URL}/queue", headers={"X-Api-Key": SONARR_API_KEY})
    if response.status_code != 200:
        print("Failed to fetch download queue.")
        print(response.text)
        return []
    return response.json()

# Function to monitor the next 5 episodes
def monitor_next_episodes(series_id, current_episode, season_number, download_queue):
    print(f"Enabling monitoring for the next 5 episodes starting from Episode {current_episode + 1} in Season {season_number}...")
    episodes_response = requests.get(f"{SONARR_API_URL}/episode",
                                     headers={"X-Api-Key": SONARR_API_KEY},
                                     params={"seriesId": series_id})
    print(f"Sonarr Episodes Response Code: {episodes_response.status_code}")
    if episodes_response.status_code != 200:
        print("Failed to fetch episodes from Sonarr.")
        print(episodes_response.text)
        return False

    episodes = episodes_response.json()
    to_update = []

    for ep in episodes:
        if ep['seasonNumber'] == season_number and current_episode < ep['episodeNumber'] <= current_episode + 5:
            if not ep['hasFile'] and not ep.get('episodeFileId', 0):  # Only update if the episode is not downloaded
                if ep['id'] not in [q['episodeId'] for q in download_queue if 'episodeId' in q]:
                    to_update.append({"id": ep["id"], "monitored": True})

    if to_update:
        print(f"Updating monitoring for {len(to_update)} episodes...")
        for episode in to_update:
            payload = {"monitored": True}
            update_response = requests.put(f"{SONARR_API_URL}/episode/{episode['id']}",
                                           headers={"X-Api-Key": SONARR_API_KEY},
                                           json=payload)
            print(f"Update Response for Episode {episode['id']}: {update_response.status_code}")
            if update_response.status_code != 200:
                print(f"Failed to update monitoring for Episode {episode['id']}.")
                print(update_response.text)

        print(f"Monitoring enabled for the next 5 episodes starting from Episode {current_episode + 1}.")

    # Trigger search for these episodes
    print(f"Triggering search for the next 5 episodes starting from Episode {current_episode + 1}...")
    search_payload = {"name": "EpisodeSearch", "seriesId": series_id, "episodeIds": [ep['id'] for ep in to_update]}
    search_response = requests.post(f"{SONARR_API_URL}/command", 
                                    headers={"X-Api-Key": SONARR_API_KEY}, 
                                    json=search_payload)
    print(f"Search Response Code: {search_response.status_code}")
    if search_response.status_code == 200:
        print(f"Search triggered for the next 5 episodes.")
    else:
        print("Failed to trigger search for the next 5 episodes.")
        print(search_response.text)

    return True

# Main logic
def main():
    while True:
        print("Checking current activity...")
        activity = get_current_activity()
        if not activity:
            print("No activity data received from Tautulli.")
        else:
            download_queue = get_download_queue()
            for stream in activity['response']['data']['sessions']:
                if stream['media_type'] == 'episode':
                    tvdb_id = int(stream['grandparent_rating_key'])  # TVDB ID from Tautulli
                    title = stream['grandparent_title']
                    season_number = int(stream['parent_media_index'])
                    current_episode = int(stream['media_index'])

                    print(f"Processing show: {title}, Season: {season_number}, Current Episode: {current_episode}")

                    # Try to look up series by TVDB ID
                    response = requests.get(f"{SONARR_API_URL}/series/lookup", 
                                            headers={"X-Api-Key": SONARR_API_KEY}, 
                                            params={"term": f"tvdb:{tvdb_id}"})
                    print(f"Sonarr Lookup Response Code: {response.status_code}")
                    if response.status_code != 200:
                        print("Failed to lookup series in Sonarr by TVDB ID.")
                        continue

                    series = response.json()

                    # Strict filtering for tvdbId and title matching
                    series = [
                        s for s in series 
                        if s.get("tvdbId") == tvdb_id and title.lower() == s.get("title", "").lower()
                    ]

                    if not series:
                        print(f"No exact match for TVDB ID: {tvdb_id}. Trying to lookup by title: {title}...")
                        response = requests.get(f"{SONARR_API_URL}/series/lookup", 
                                                headers={"X-Api-Key": SONARR_API_KEY}, 
                                                params={"term": title})
                        print(f"Sonarr Title Lookup Response Code: {response.status_code}")
                        if response.status_code != 200:
                            print("Failed to lookup series in Sonarr by title.")
                            continue

                        # Log all results for debugging
                        title_results = response.json()
                        print(f"Title Search Results: {json.dumps(title_results, indent=2)}")

                        # Strict matching by title
                        series = [
                            s for s in title_results
                            if title.lower() == s.get("title", "").lower()
                        ]

                    if not series:
                        print(f"Series not found in Sonarr by either TVDB ID: {tvdb_id} or title: {title}.")
                        continue

                    # Validate series result
                    series_id = series[0].get('id') if series and 'id' in series[0] else None
                    if not series_id:
                        print(f"Series lookup result does not contain a valid ID. Skipping: {series[0]}")
                        continue

                    if monitor_next_episodes(series_id, current_episode, season_number, download_queue):
                        print(f"Monitoring and search enabled for the next 5 episodes of {title}, Season {season_number}.")
        print("Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main()
