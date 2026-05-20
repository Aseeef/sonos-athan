import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from adhanpy.calculation.CalculationMethod import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.Madhab import Madhab
from adhanpy.PrayerTimes import PrayerTimes

from .config import logger, LATITUDE, LONGITUDE, TIMEZONE, CALCULATION_METHOD, MADHAB, REMIND_BEFORE_MINUTES, ATHAN_FILENAME, FAJR_ATHAN_FILENAME, PLAY_ATHAN_FOR
from .sonos import SonosManager
from .audio import generate_reminder

class AthanScheduler:
    def __init__(self, debug=False):
        self.sonos = SonosManager()
        self.current_day = None
        self.prayer_times = {}
        self.debug = debug
        self.stop_event = threading.Event()
        self.local_tz = ZoneInfo(TIMEZONE)

    def get_calc_method(self):
        method = getattr(CalculationMethod, CALCULATION_METHOD, None)
        return method or CalculationMethod.NORTH_AMERICA

    def get_madhab(self):
        madhab = getattr(Madhab, MADHAB, None)
        return madhab or Madhab.SHAFI

    def update_times(self):
        now_local = datetime.now(self.local_tz)
        today = now_local.date()
        if self.current_day != today:
            logger.info(f"Calculating prayer times for {today} in {TIMEZONE}...")
            try:
                calc_method = self.get_calc_method()
                madhab = self.get_madhab()
                params = CalculationParameters(method=calc_method)
                params.madhab = madhab
                
                # Get times for today
                times = PrayerTimes((LATITUDE, LONGITUDE), now_local, calculation_parameters=params, time_zone=self.local_tz)
                
                # Midnight calculation requires tomorrow's Fajr
                tomorrow_local = now_local + timedelta(days=1)
                tomorrow_times = PrayerTimes((LATITUDE, LONGITUDE), tomorrow_local, calculation_parameters=params, time_zone=self.local_tz)
                
                maghrib = times.maghrib
                next_fajr = tomorrow_times.fajr
                duration = next_fajr - maghrib
                midnight = maghrib + (duration / 2)
                
                self.prayer_times = {
                    "Fajr": times.fajr,
                    "Sunrise": times.sunrise,
                    "Dhuhr": times.dhuhr,
                    "Asr": times.asr,
                    "Maghrib": times.maghrib,
                    "Isha": times.isha,
                    "Midnight": midnight
                }
                self.current_day = today
                for name, t in self.prayer_times.items():
                    logger.info(f"{name}: {t.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                return True
            except Exception as e:
                logger.error(f"Error calculating prayer times: {e}. Will retry in 1 minute.")
                return False
        return True

    def run(self):
        # Initial discovery
        logger.info("Performing initial Sonos discovery...")
        self.sonos.discover_and_group(debug=self.debug)

        if self.debug:
            logger.info("DEBUG MODE: Triggering Athan immediately.")
            threading.Thread(target=self.sonos.play, args=(ATHAN_FILENAME, True), daemon=True).start()

        while not self.stop_event.is_set():
            if not self.update_times():
                # If calculation failed (e.g. internet blip), wait a bit and retry the loop
                self.stop_event.wait(60)
                continue

            now = datetime.now(self.local_tz)
            events = []
            for name, p_time in self.prayer_times.items():
                if name in ["Sunrise", "Midnight"]:
                    msg = "Fajr prayer time has ended" if name == "Sunrise" else "The preferred time for Isha has ended"
                    events.append((p_time, "announcement", name, msg))
                else:
                    events.append((p_time, "athan", name, 0))
                    for minutes in REMIND_BEFORE_MINUTES:
                        reminder_time = p_time - timedelta(minutes=minutes)
                        events.append((reminder_time, "reminder", name, minutes))

            # Filter for future events only
            future_events = sorted([e for e in events if e[0] > now], key=lambda x: x[0])

            if not future_events:
                # End of day, wait for midnight calculation in next loop
                logger.info("No more events today. Waiting for tomorrow...")
                self.stop_event.wait(60)
                continue

            next_event = future_events[0]
            next_event_time = next_event[0]
            event_type = next_event[1]
            prayer_name = next_event[2]
            
            wait_seconds = (next_event_time - now).total_seconds()
            
            # Instead of one long sleep, sleep in 30s chunks
            # to handle system clock drift (NTP jumps) and signal responsiveness.
            if wait_seconds > 30:
                if self.debug: logger.info(f"Waiting for {prayer_name} ({event_type}) in {wait_seconds:.0f}s...")
                self.stop_event.wait(30)
                continue # Re-check everything in the next loop iteration

            # We are within 30 seconds of the event - perform final precision wait
            if wait_seconds > 0:
                if self.stop_event.wait(wait_seconds): break
            
            # Execute event
            logger.info(f"Executing: {event_type} for {prayer_name}")
            if event_type == "athan":
                if prayer_name in PLAY_ATHAN_FOR:
                    file = FAJR_ATHAN_FILENAME if prayer_name == "Fajr" else ATHAN_FILENAME
                    self.sonos.play(file, debug=self.debug)
                else:
                    msg = f"{prayer_name} prayer time has started"
                    self.sonos.play(generate_reminder(prayer_name, 0, custom_text=msg), debug=self.debug)
            elif event_type == "announcement":
                self.sonos.play(generate_reminder(prayer_name, 0, custom_text=next_event[3]), debug=self.debug)
            else:
                self.sonos.play(generate_reminder(prayer_name, next_event[3]), debug=self.debug)

    def shutdown(self):
        logger.info("Shutting down scheduler...")
        self.stop_event.set()
        if self.sonos.is_playing_athan:
            self.sonos.restore_state(debug=self.debug)
