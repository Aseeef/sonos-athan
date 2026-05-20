import time
import socket
import soco
from .config import logger, SONOS_SPEAKER_NAMES, ATHAN_VOLUME, SERVER_PORT, MANUAL_IP

# Globals for dynamic detection
DETECTED_IP = None

def get_local_ip(target_ip=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(2)
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
        self.target_ips = []
        self.is_playing_athan = False
        self.original_states = {} # Store state per speaker/group

    def discover_and_group(self, debug=False):
        try:
            potential_speakers = []
            if self.target_ips:
                for ip in self.target_ips:
                    try:
                        s = soco.SoCo(ip)
                        _ = s.player_name
                        potential_speakers.append(s)
                    except: pass
            
            if not potential_speakers or (self.speaker_names and len(potential_speakers) < len(self.speaker_names)):
                logger.info("Scanning network for Sonos speakers via multicast...")
                all_speakers = soco.discover(timeout=5)
                if all_speakers: potential_speakers = list(all_speakers)
            
            if not potential_speakers:
                logger.warning("No Sonos speakers found.")
                return False

            self.target_speakers = []
            new_ips = []
            for s in potential_speakers:
                try:
                    name = s.player_name
                    # Always log discovered speakers that match configuration
                    if not self.speaker_names or name in self.speaker_names:
                        logger.info(f" - Configured Speaker: {name} ({s.ip_address})")
                        self.target_speakers.append(s)
                        new_ips.append(s.ip_address)
                    elif debug:
                        logger.info(f" - Found (unconfigured): {name} ({s.ip_address})")
                except Exception as e:
                    if debug: logger.warning(f" - Error communicating with {s.ip_address}: {e}")
                    continue

            if not self.target_speakers:
                logger.warning("None of the target speakers were found.")
                return False

            self.target_ips = new_ips
            self.target_speakers.sort(key=lambda x: x.ip_address)
            self.master = self.target_speakers[0]
            
            return True
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return False

    def play(self, filename, debug=False):
        global DETECTED_IP
        if not self.discover_and_group(debug=debug): return

        callback_ip = MANUAL_IP or DETECTED_IP
        if not callback_ip:
            DETECTED_IP = get_local_ip(self.master.ip_address)
            callback_ip = DETECTED_IP

        uri = f"http://{callback_ip}:{SERVER_PORT}/{filename}"
        
        try:
            # 1. SAVE COMPREHENSIVE STATE
            # We save the grouping and playback state for EVERY target speaker
            self.original_states = {}
            for s in self.target_speakers:
                try:
                    # Capture if this speaker was a coordinator of its own group
                    is_coord = s.is_coordinator
                    coord_ip = s.group.coordinator.ip_address
                    
                    state = {
                        'volume': s.volume,
                        'is_coordinator': is_coord,
                        'original_coordinator_ip': coord_ip,
                        'transport_info': None,
                        'track_info': None
                    }
                    
                    # If it was a coordinator, save what it was playing
                    if is_coord:
                        state['transport_info'] = s.get_current_transport_info()
                        state['track_info'] = s.get_current_track_info()
                    
                    self.original_states[s.ip_address] = state
                except Exception as e:
                    logger.warning(f"Could not capture state for {s.player_name}: {e}")

            if debug: logger.info(f"Captured state for {len(self.original_states)} speakers.")

            # 2. GROUP FOR ATHAN
            if len(self.target_speakers) > 1:
                logger.info(f"Regrouping {len(self.target_speakers)} speakers for announcement...")
                for speaker in self.target_speakers:
                    try: speaker.unjoin()
                    except: pass
                time.sleep(1)
                for speaker in self.target_speakers:
                    if speaker.ip_address != self.master.ip_address:
                        try: speaker.join(self.master)
                        except: pass
                time.sleep(2)

            self.is_playing_athan = True

            # 3. SET VOLUME & PLAY
            if ATHAN_VOLUME:
                for s in self.target_speakers:
                    try: s.volume = ATHAN_VOLUME
                    except: pass

            logger.info(f"Playing announcement on {self.master.player_name} group...")
            
            try:
                self.master.play_uri(uri)
                
                # 4. WAIT
                time.sleep(3)
                max_wait = 300
                start_wait = time.time()
                while time.time() - start_wait < max_wait and self.is_playing_athan:
                    try:
                        curr_state = self.master.get_current_transport_info().get('current_transport_state')
                        if debug: logger.info(f"State: {curr_state}")
                        if curr_state not in ['PLAYING', 'TRANSITIONING']: break
                    except: pass
                    if self.is_playing_athan:
                        time.sleep(2)
            except Exception as playback_err:
                logger.error(f"Playback command failed: {playback_err}")
                
        except Exception as e:
            logger.error(f"Unexpected error in play sequence: {e}")
        finally:
            # 5. ALWAYS RESTORE
            self.is_playing_athan = False # Ensure loop breaks if it hasn't
            self.restore_state(debug=debug)

    def restore_state(self, debug=False):
        if not self.original_states:
            return

        logger.info("Restoring original Sonos groups and playback state...")
        
        # Step A: Restore Grouping & Volumes
        for s in self.target_speakers:
            state = self.original_states.get(s.ip_address)
            if not state: continue
            
            try:
                # Restore volume first so it's quiet/correct before music starts
                s.volume = state['volume']
                
                # Restore Group status
                orig_coord_ip = state['original_coordinator_ip']
                if orig_coord_ip == s.ip_address:
                    s.unjoin()
                else:
                    try:
                        coord = soco.SoCo(orig_coord_ip)
                        s.join(coord)
                    except:
                        s.unjoin()
            except Exception as e:
                if debug: logger.warning(f"Error restoring basic state for {s.player_name}: {e}")

        time.sleep(2) # Wait for regrouping to settle

        # Step B: Restore Playback for the coordinators
        for s in self.target_speakers:
            state = self.original_states.get(s.ip_address)
            if not state or not state['is_coordinator']: continue
            
            try:
                track = state['track_info']
                trans = state['transport_info']
                
                if track and track.get('uri'):
                    try:
                        s.play_uri(track['uri'], title=track.get('title'))
                        if track.get('position') and track['position'] != '0:00:00':
                            try: s.seek(track['position'])
                            except: pass
                    except: pass
                
                if trans:
                    target_ts = trans.get('current_transport_state')
                    if target_ts == 'PLAYING': s.play()
                    elif target_ts == 'PAUSED': s.pause()
                    else: s.stop()
            except Exception as e:
                if debug: logger.warning(f"Error restoring playback for {s.player_name}: {e}")

        self.original_states = {}
