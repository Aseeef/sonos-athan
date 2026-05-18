import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from adhanpy.calculation.CalculationMethod import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.Madhab import Madhab
from adhanpy.PrayerTimes import PrayerTimes

from .config import logger, LATITUDE, LONGITUDE, TIMEZONE, CALCULATION_METHOD, MADHAB, REMIND_BEFORE_MINUTES, ATHAN_FILENAME, FAJR_ATHAN_FILENAME
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
            calc_method = self.get_calc_method()
            madhab = self.get_madhab()
            params = CalculationParameters(method=calc_method)
            params.madhab = madhab
            
            times = PrayerTimes((LATITUDE, LONGITUDE), now_local, calculation_parameters=params, time_zone=self.local_tz)
            
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

    def run(self):
        if self.debug:
            logger.info("DEBUG MODE: Triggering Athan immediately.")
            threading.Thread(target=self.sonos.play, args=(ATHAN_FILENAME, True), daemon=True).start()

        while not self.stop_event.is_set():
            self.update_times()
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

            future_events = sorted([e for e in events if e[0] > now], key=lambda x: x[0])

            if not future_events:
                tomorrow_midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=self.local_tz)
                wait_seconds = (tomorrow_midnight - now).total_seconds() + 5
                logger.info(f"Sleeping until tomorrow...")
                if self.stop_event.wait(wait_seconds): break
                continue

            next_event = future_events[0]
            next_event_time = next_event[0]
            event_type = next_event[1]
            prayer_name = next_event[2]
            
            wait_seconds = (next_event_time - now).total_seconds()
            logger.info(f"Next: {event_type} for {prayer_name} at {next_event_time.strftime('%H:%M:%S')} (in {wait_seconds:.0f}s)")
            
            if self.stop_event.wait(wait_seconds): break
            
            if event_type == "athan":
                file = FAJR_ATHAN_FILENAME if prayer_name == "Fajr" else ATHAN_FILENAME
                self.sonos.play(file, debug=self.debug)
            elif event_type == "announcement":
                custom_text = next_event[3]
                self.sonos.play(generate_reminder(prayer_name, 0, custom_text=custom_text), debug=self.debug)
            else:
                reminder_mins = next_event[3]
                self.sonos.play(generate_reminder(prayer_name, reminder_mins), debug=self.debug)

    def shutdown(self):
        logger.info("Shutting down scheduler and cleaning up Sonos...")
        self.stop_event.set()
        if self.sonos.is_playing_athan:
            self.sonos.restore_state(debug=self.debug)
