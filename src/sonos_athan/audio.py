import os
import requests
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from gtts import gTTS
from .config import logger, AUDIO_DIR, ATHAN_AUDIO_URL, FAJR_ATHAN_AUDIO_URL, ATHAN_PATH, FAJR_ATHAN_PATH

class AudioServerThread(threading.Thread):
    def __init__(self, port, directory):
        super().__init__(daemon=True)
        self.port = port
        self.directory = os.path.abspath(directory)
        self.httpd = None

    def run(self):
        directory = self.directory
        class CustomHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
            def log_message(self, format, *args): pass
            def handle_one_request(self):
                try: super().handle_one_request()
                except (ConnectionResetError, BrokenPipeError): pass

        self.httpd = ThreadingHTTPServer(('', self.port), CustomHandler)
        logger.info(f"Audio server started on port {self.port}, serving {self.directory}")
        self.httpd.serve_forever()

    def shutdown(self):
        if self.httpd:
            self.httpd.shutdown()

def download_audio(url, path, label):
    if not os.path.exists(path):
        logger.info(f"Downloading {label} from {url}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, 'wb') as f:
                f.write(response.content)
            logger.info(f"{label} downloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to download {label}: {e}")

def download_all_audio():
    if not os.path.exists(AUDIO_DIR):
        os.makedirs(AUDIO_DIR)
    download_audio(ATHAN_AUDIO_URL, ATHAN_PATH, "Athan")
    download_audio(FAJR_ATHAN_AUDIO_URL, FAJR_ATHAN_PATH, "Fajr Athan")

def generate_reminder(prayer_name, minutes, custom_text=None):
    if custom_text:
        import hashlib
        text_hash = hashlib.md5(custom_text.encode()).hexdigest()[:8]
        filename = f"custom_{text_hash}.mp3"
        text = custom_text
    else:
        filename = f"reminder_{prayer_name}_{minutes}.mp3"
        text = f"{prayer_name} prayer starts in {minutes} minutes."
    
    path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(path):
        logger.info(f"Generating TTS: '{text}'")
        try:
            tts = gTTS(text=text, lang='en')
            tts.save(path)
        except Exception as e:
            logger.error(f"Failed to generate TTS: {e}")
    return filename
