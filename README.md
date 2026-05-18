# SonosAthan

> **Disclaimer:** This project was 100% vibe coded with [Gemini CLI](https://github.com/google-gemini/gemini-cli).

A robust, 24/7 Sonos Athan player with automated scheduling, smart reminders, and non-disruptive playback. Calculated using the `adhanpy` library.

## Key Features
- **24/7 Automated Scheduling:** Calculates prayer times daily at midnight and schedules events automatically.
- **Non-Disruptive Playback:** Captures the current state of your Sonos speakers (track, volume, play/pause, seek position), plays the Athan, and then **fully restores** your music exactly where it left off.
- **Multi-Interval Reminders:** Configurable reminders (e.g., "Asr prayer starts in 15 minutes") at multiple time intervals before each prayer.
- **Sunrise & Midnight Announcements:** Optional TTS announcements for the end of Fajr and the end of the preferred time for Isha.
- **Grouped Playback:** Automatically discovers your Sonos speakers and groups them for perfectly synchronized audio across your home.
- **Smart Network Detection:** Dynamically detects the correct local network interface to ensure your Sonos speakers can always reach the internal audio server.
- **Professional Packaging:** Built with modern Python standards (`pyproject.toml`) and optimized for Docker.

## Configuration (.env)

The program is fully configurable via environment variables or a `.env` file.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LATITUDE` | Latitude for prayer time calculation | `40.7128` (NYC) |
| `LONGITUDE` | Longitude for prayer time calculation | `-74.0060` (NYC) |
| `TIMEZONE` | Timezone for calculations and logs (e.g., `Europe/London`) | `America/New_York` |
| `CALCULATION_METHOD` | Calculation method (e.g., `NORTH_AMERICA`, `UMM_AL_QURA`) | `NORTH_AMERICA` (ISNA) |
| `MADHAB` | Madhab for Asr calculation (`SHAFI` or `HANAFI`) | `SHAFI` |
| `REMIND_BEFORE_MINUTES` | Comma-separated minutes for reminders (e.g., `5,15,30`) | `0` (Disabled) |
| `SONOS_SPEAKER_NAMES` | Comma-separated names of speakers to use (leave empty for all) | (All discovered) |
| `ATHAN_VOLUME` | Fixed volume level (0-100) for Athan playback | (Original Volume) |
| `ATHAN_AUDIO_URL` | URL for the regular Athan MP3 | (Makkah Athan) |
| `FAJR_ATHAN_AUDIO_URL` | URL for the Fajr Athan MP3 | (Fajr Athan) |
| `LOCAL_IP` | Manually set host IP if auto-detection fails | (Auto-detected) |
| `SERVER_PORT` | Port for the built-in HTTP audio server | `8000` |

### Supported Calculation Methods
`MUSLIM_WORLD_LEAGUE`, `NORTH_AMERICA` (ISNA), `EGYPTIAN`, `KARACHI`, `UMM_AL_QURA`, `DUBAI`, `MOON_SIGHTING_COMMITTEE`, `SINGAPORE`, `TURKEY`, `TEHRAN`, `QATAR`, `KUWAIT`.

## Deployment

### Using Docker (Recommended)
The easiest way to run SonosAthan is using Docker Compose. Ensure you have `network_mode: host` set to allow Sonos discovery.

> **Note on Rootless Docker/Podman:** This program relies heavily on host networking to discover speakers and handle callbacks. It is not currently designed to work out-of-the-box with Rootless Docker or Podman due to the networking isolation provided by those environments. While it's possible to get it working with additional configuration, the level of isolation wasn't considered necessary for a tool intended strictly for local network use.

1.  **Clone the repository.**
2.  **Configure your settings** in the `.env` file.
3.  **Start the container:**
    ```bash
    docker compose up -d --build
    ```

### Local Installation
1.  **Install dependencies:**
    ```bash
    pip install -e .
    ```
2.  **Run the program:**
    ```bash
    sonos-athan
    ```

## Debugging & Testing
You can trigger an immediate Athan playback and see detailed speaker discovery information by using the `--debug` flag:
```bash
sonos-athan --debug
```

## Graceful Cleanup
The program handles termination signals (`SIGINT`, `SIGTERM`) gracefully. If you stop the program (e.g., `Ctrl+C`) while an Athan is playing, it will automatically stop the audio and restore your speakers to their original state before exiting.
