import subprocess
import sys
import threading
import time
from pathlib import Path

restart = threading.Event()
shutdown = threading.Event()
MANUAL_COUNTDOWN_PATH = Path("data/manual_countdown_timestamp.txt")

def console_listener():
    while True:
        cmd = input().strip()

        if cmd == "":
            restart.set()

        elif cmd.lower() == "q":
            confirm = input("Shutdown server? (y/n): ").strip().lower()

            if confirm in ("y", "yes"):
                shutdown.set()
                return
            else:
                print("Shutdown cancelled", flush=True)

        else:
            try:
                float(cmd)
            except ValueError:
                print(
                    "Enter a Unix timestamp, press Enter to restart, or type q to quit.",
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