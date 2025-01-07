# Chronicle

Created due to server size constraints but wanting to grow my library ever-more.

This Python script integrates **Tautulli** and **Sonarr** to automate the monitoring and searching of TV series episodes based on user activity. It identifies TV shows being watched in Tautulli and ensures the corresponding episodes and subsequent episodes are monitored and searched in Sonarr. T

---

## Features

- **Fetch Activity from Tautulli**: Detects currently watched episodes from Tautulli's API.
- **Automate Monitoring in Sonarr**: Enables monitoring for the next 5 episodes of a series.
- **Trigger Searches in Sonarr**: Automatically triggers searches for the monitored episodes to download them.
- **Strict Matching**: Matches TV series by **TVDB ID** and title for accurate results.
- **Download Queue Handling**: Skips episodes already in the download queue to avoid duplicates.

---

## Prerequisites

1. **Python 3.x**: Ensure Python 3.x is installed on your system.
2. **Tautulli API**: Your Tautulli server must be running and configured with API access.
3. **Sonarr API**: Your Sonarr server must be running and configured with API access.
4. **Plex Media Server**: Tautulli should be configured to monitor your Plex activity.

---

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/iwouldratherbeatthebeach/chronicle.git
   cd chronicle
   ```

2. Install the required dependencies:
   ```bash
   pip install requests
   ```

3. Configure the script:
   - Open the script file in a text editor.
   - Replace the placeholders with your server information:
     - `TAUTULLI_API_URL`
     - `TAUTULLI_API_KEY`
     - `SONARR_API_URL`
     - `SONARR_API_KEY`

---

## Usage

1. Run the script:
   ```bash
   python chronicle.py
   ```

2. The script will:
   - Fetch current activity from Tautulli.
   - Match series with Sonarr by TVDB ID or title.
   - Enable monitoring for the next 5 episodes.
   - Trigger searches for the monitored episodes.

---

## Troubleshooting

- **Invalid Matches**: If the script matches the wrong series (e.g., foreign titles), ensure:
  - Your Sonarr library is properly configured.
  - TVDB IDs in Tautulli match those in Sonarr.

- **API Errors**: Check the connectivity and API keys for Tautulli and Sonarr.

- **Debugging**: The script logs detailed output, including API responses, to help identify issues.

---

## Example Output

```plaintext
Fetching current activity from Tautulli...
Tautulli Response Code: 200
Processing show: Below Deck, Season: 4, Current Episode: 1
Sonarr Lookup Response Code: 200
Enabling monitoring for the next 5 episodes starting from Episode 2 in Season 4...
Triggering search for the next 5 episodes...
Search Response Code: 201
Monitoring and search enabled for the next 5 episodes of Below Deck, Season 4.
```



