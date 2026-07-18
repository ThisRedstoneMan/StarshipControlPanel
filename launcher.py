import subprocess
import sys
import threading
import time

restart = threading.Event()
shutdown = threading.Event()

def console_listener():
    while True:
        cmd = input().strip().lower()

        if cmd == "":
            restart.set()

        elif cmd == "q":
            confirm = input("Shutdown server? (y/n): ").strip().lower()

            if confirm in ("y", "yes"):
                shutdown.set()
                return
            else:
                print("Shutdown cancelled")

threading.Thread(target=console_listener, daemon=True).start()

while True:
    print("Launching server.py")

    server = subprocess.Popen(
        [sys.executable, "server.py"]
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