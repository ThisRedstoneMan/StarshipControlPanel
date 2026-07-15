import platform
import sys

def trigger_system_beep(frequency=800, duration_ms=250):
    current_os = platform.system().lower()
    if current_os == "windows":
        import winsound
        winsound.Beep(frequency, duration_ms)
    else:
        sys.stderr.write('\a')
        sys.stderr.flush()