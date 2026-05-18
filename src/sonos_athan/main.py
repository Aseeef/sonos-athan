import signal
import sys
import argparse
from .config import logger, SERVER_PORT, AUDIO_DIR
from .audio import AudioServerThread, download_all_audio
from .scheduler import AthanScheduler

def main():
    parser = argparse.ArgumentParser(description="Sonos Athan Player")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Initial setup
    download_all_audio()

    # Start services
    server = AudioServerThread(SERVER_PORT, AUDIO_DIR)
    server.start()

    scheduler = AthanScheduler(debug=args.debug)
    
    def signal_handler(sig, frame):
        logger.info(f"Signal {sig} received. Cleaning up...")
        # Shutdown scheduler first to stop Sonos playback and restore state
        scheduler.shutdown()
        # Shutdown server
        server.shutdown()
        logger.info("Cleanup complete. Exiting.")
        sys.exit(0)

    # Register handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        scheduler.run()
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        scheduler.shutdown()
        server.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()
