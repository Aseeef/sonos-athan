import os
import logging
import sys
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

import soco
# Set global network timeout for all Sonos interactions (seconds)
soco.config.NETWORK_TIMEOUT = 5.0

# --- Core Configuration ---
LATITUDE = float(os.getenv('LATITUDE', '40.7128'))
LONGITUDE = float(os.getenv('LONGITUDE', '-74.0060'))
TIMEZONE = os.getenv('TIMEZONE', 'America/New_York')
CALCULATION_METHOD = os.getenv('CALCULATION_METHOD', 'NORTH_AMERICA').upper()
MADHAB = os.getenv('MADHAB', 'SHAFI').upper()

# Sonos
SONOS_SPEAKER_NAMES = [name.strip() for name in os.getenv('SONOS_SPEAKER_NAMES', '').split(',') if name.strip()]
ATHAN_VOLUME = os.getenv('ATHAN_VOLUME')
ATHAN_VOLUME = int(ATHAN_VOLUME) if ATHAN_VOLUME else None

# Reminders
REMIND_BEFORE_MINUTES_STR = os.getenv('REMIND_BEFORE_MINUTES', '0')
REMIND_BEFORE_MINUTES = [int(m.strip()) for m in REMIND_BEFORE_MINUTES_STR.split(',') if m.strip().isdigit() and int(m.strip()) > 0]

# Audio
ATHAN_AUDIO_URL = os.getenv('ATHAN_AUDIO_URL', 'https://media.assabile.com/assabile/adhan_3435370/6f509ec934a4.mp3')
FAJR_ATHAN_AUDIO_URL = os.getenv('FAJR_ATHAN_AUDIO_URL', 'https://media.assabile.com/assabile/adhan_3435370/ddb21f7363eb.mp3')
PLAY_ATHAN_FOR = [p.strip().capitalize() for p in os.getenv('PLAY_ATHAN_FOR', 'Fajr,Dhuhr,Asr,Maghrib,Isha').split(',') if p.strip()]
SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))
AUDIO_DIR = os.getenv('AUDIO_DIR', 'audio')

# Network
MANUAL_IP = os.getenv('LOCAL_IP')

# Constants
ATHAN_FILENAME = "athan.mp3"
FAJR_ATHAN_FILENAME = "fajr_athan.mp3"
ATHAN_PATH = os.path.join(AUDIO_DIR, ATHAN_FILENAME)
FAJR_ATHAN_PATH = os.path.join(AUDIO_DIR, FAJR_ATHAN_FILENAME)

# --- Logging Setup ---
class TZFormatter(logging.Formatter):
    def converter(self, timestamp):
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp, tz=ZoneInfo(TIMEZONE))
        return dt.timetuple()

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.getLogger().handlers[0].setFormatter(TZFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    return logging.getLogger("sonos_athan")

logger = setup_logging()
