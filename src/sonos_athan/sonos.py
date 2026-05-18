import time
import socket
import soco
from .config import logger, SONOS_SPEAKER_NAMES, ATHAN_VOLUME, SERVER_PORT, MANUAL_IP

# Globals for dynamic detection
DETECTED_IP = None

def get_local_ip(target_ip=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip or '1.1.1.1', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class SonosManager:
    def __init__(self, speaker_names=SONOS_SPEAKER_NAMES):
        self.speaker_names = speaker_names
        self.master = None
        self.target_speakers = []
        self.is_playing_athan = False
        self.original_state = {}

    def discover_and_group(self, debug=False):
        try:
            logger.info("Scanning network for Sonos speakers...")
            all_speakers = soco.discover(timeout=5)
            if not all_speakers:
                logger.warning("No Sonos speakers found on the network.")
                return False

            if debug:
                logger.info(f"Discovered {len(all_speakers)} potential devices. Fetching info...")

            self.target_speakers = []
            for s in all_speakers:
                try:
                    name = s.player_name
                    if debug: logger.info(f" - Found: {name} ({s.ip_address})")
                    if not self.speaker_names or name in self.speaker_names:
                        self.target_speakers.append(s)
                except Exception as e:
                    if debug: logger.warning(f" - Error communicating with {s.ip_address}: {e}")
                    continue

            if not self.target_speakers:
                logger.warning(f"None of the target speakers {self.speaker_names} were found.")
                return False

            self.target_speakers.sort(key=lambda x: x.ip_address)
            self.master = self.target_speakers[0]
            logger.info(f"Using {self.master.player_name} ({self.master.ip_address}) as master.")
            
            if len(self.target_speakers) > 1:
                logger.info(f"Grouping {len(self.target_speakers)} speakers...")
                for speaker in self.target_speakers:
                    if speaker != self.master:
                        try: speaker.join(self.master)
                        except Exception as e: logger.error(f"Failed to join {speaker.ip_address}: {e}")
            return True
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return False

    def play(self, filename, debug=False):
        global DETECTED_IP
        if not self.master:
            if not self.discover_and_group(debug=debug): return

        callback_ip = MANUAL_IP or DETECTED_IP
        if not callback_ip:
            DETECTED_IP = get_local_ip(self.master.ip_address)
            callback_ip = DETECTED_IP
            logger.info(f"Auto-detected local IP: {callback_ip}")

        uri = f"http://{callback_ip}:{SERVER_PORT}/{filename}"
        logger.info(f"Playing {uri} on Sonos...")
        
        try:
            # 1. Save current state for ALL target speakers
            state = self.master.get_current_transport_info()
            self.original_state = {
                'transport_state': state.get('current_transport_state'),
                'track': self.master.get_current_track_info(),
                'volumes': {s.ip_address: s.volume for s in self.target_speakers}
            }
            self.is_playing_athan = True

            if debug:
                logger.info(f"Original State: {self.original_state['transport_state']}")
                logger.info(f"Original Volumes: {self.original_state['volumes']}")
            
            # 2. Set Volume for all speakers in the group
            if ATHAN_VOLUME:
                for s in self.target_speakers:
                    try: s.volume = ATHAN_VOLUME
                    except: pass

            # 3. Play our audio
            self.master.play_uri(uri)
            
            # 4. Wait for our audio to finish
            time.sleep(3)
            max_wait = 300
            start_wait = time.time()
            while time.time() - start_wait < max_wait and self.is_playing_athan:
                try:
                    current_info = self.master.get_current_transport_info()
                    curr_state = current_info.get('current_transport_state')
                    if debug: logger.info(f"Current Transport State: {curr_state}")
                    if curr_state not in ['PLAYING', 'TRANSITIONING']:
                        break
                except:
                    # Connection might be flaky during group changes
                    pass
                time.sleep(2)
            
            # 5. Restore state
            self.restore_state(debug=debug)
                
        except Exception as e:
            logger.error(f"Failed to play on Sonos: {e}")
            self.is_playing_athan = False

    def restore_state(self, debug=False):
        # Ensure we don't try to restore twice or if not playing
        if not self.master or not self.original_state:
            return

        logger.info("Restoring original Sonos state...")
        try:
            # Restore Volumes for all speakers
            volumes = self.original_state.get('volumes', {})
            for s in self.target_speakers:
                if s.ip_address in volumes:
                    try:
                        logger.info(f"Restoring volume for {s.player_name} to {volumes[s.ip_address]}")
                        s.volume = volumes[s.ip_address]
                    except Exception as e:
                        logger.warning(f"Could not restore volume for {s.ip_address}: {e}")

            # Restore Track
            track = self.original_state.get('track', {})
            if track.get('uri'):
                try:
                    self.master.play_uri(track['uri'], title=track.get('title'))
                    if track.get('position') and track['position'] != '0:00:00':
                        try: self.master.seek(track['position'])
                        except: pass
                except Exception as e:
                    if debug: logger.warning(f"Could not restore track URI: {e}")
            
            # Restore Transport State
            state = self.original_state.get('transport_state')
            if state == 'PLAYING': self.master.play()
            elif state == 'PAUSED': self.master.pause()
            else: self.master.stop()

        except Exception as e:
            logger.error(f"Error during state restoration: {e}")
        finally:
            self.is_playing_athan = False
            self.original_state = {}
