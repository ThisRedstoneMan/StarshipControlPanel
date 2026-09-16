import subprocess
import sys
import threading

try:
    import msvcrt
except ImportError:
    msvcrt = None
import time
from pathlib import Path

restart = threading.Event()
shutdown = threading.Event()
MANUAL_COUNTDOWN_PATH = Path("data/manual_countdown_timestamp.txt")
NETWORK_STATS_SIGNAL_PATH = Path("data/network_stats_request.flag")
FLIGHT_ID_REQUEST_PATH = Path("data/flight_id_request.txt")
FLIGHT_ID_RESPONSE_PATH = Path("data/flight_id_response.txt")

def _handle_flight_id_request():
    """Prompt for a replacement Flight ID requested by main.py."""
    if not FLIGHT_ID_REQUEST_PATH.exists():
        return

    try:
        invalid_flight_id = FLIGHT_ID_REQUEST_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return

    print(
        f"\nFlight ID '{invalid_flight_id}' was not found on the first SpaceX fetch.",
        flush=True,
    )

    while True:
        try:
            new_flight_id = input("Enter a new Flight ID: ").strip()
        except EOFError:
            print("Unable to read a new Flight ID from stdin.", flush=True)
            return

        if new_flight_id:
            break

        print("Flight ID cannot be empty. Please enter a new Flight ID.", flush=True)

    FLIGHT_ID_RESPONSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLIGHT_ID_RESPONSE_PATH.write_text(new_flight_id, encoding="utf-8")

    try:
        FLIGHT_ID_REQUEST_PATH.unlink()
    except FileNotFoundError:
        pass

    print(f"New Flight ID supplied: {new_flight_id}", flush=True)


def console_listener():
    while True:
        _handle_flight_id_request()

        if msvcrt is not None:
            # Windows consoles do not support select() on sys.stdin. Poll
            # for a key instead, while still checking for a Flight ID request
            # every loop.
            if not msvcrt.kbhit():
                time.sleep(0.2)
                continue

        elif not sys.stdin.isatty():
            # Non-interactive stdin: there is no safe cross-platform way to
            # poll it without potentially blocking this thread. Keep checking
            # for launcher requests instead.
            time.sleep(0.2)
            continue
        else:
            import select
            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not ready:
                continue

        try:
            cmd = input().strip()
        except EOFError:
            return

        if cmd == "":
            restart.set()

        elif cmd.lower() == "q":
            confirm = input("Shutdown server? (y/n): ").strip().lower()

            if confirm in ("y", "yes"):
                shutdown.set()
                return
            else:
                print("Shutdown cancelled", flush=True)

        elif cmd.lower() == "network":
            NETWORK_STATS_SIGNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            NETWORK_STATS_SIGNAL_PATH.write_text("1", encoding="ascii")
            print("Requested endpoint connection stats - check server output.", flush=True)

        else:
            try:
                float(cmd)
            except ValueError:
                print(
                    "Enter a Unix timestamp, press Enter to restart, "
                    "type 'network' for endpoint connection stats, or type q to quit.",
                    flush=True,
                )
            else:
                MANUAL_COUNTDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
                MANUAL_COUNTDOWN_PATH.write_text(cmd, encoding="ascii")
                print(f"Temporary countdown timestamp set to {cmd}", flush=True)

threading.Thread(target=console_listener, daemon=True).start()

while True:
    print("Launching server.py", flush=True)

    server = subprocess.Popen(
        [sys.executable, "-u", "server.py"]
    )

    while True:
        if shutdown.is_set():
            print("Shutting down...")

            server.terminate()

            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing server")
                server.kill()

            print("Server closed")
            sys.exit(0)

        if restart.is_set():
            print("Restart requested")

            server.terminate()

            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing server")
                server.kill()

            restart.clear()
            print("Restarting...\n")
            break

        # Server crashed
        if server.poll() is not None:
            print("Server exited unexpectedly")
            break

        time.sleep(0.2)