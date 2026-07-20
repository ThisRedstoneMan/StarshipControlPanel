import os
import platform
import sys
import time

def trigger_system_beep(frequency, duration_ms):
    """Triggers a basic system beep across Windows, macOS, and Linux without external audio packages."""
    current_os = platform.system().lower()
    if current_os == "windows":
        import winsound
        winsound.Beep(frequency, duration_ms)
    elif current_os == "darwin":  # macOS
        os.system("osascript -e 'beep'")
    else:  # Linux / Unix
        sys.stderr.write('\a')
        sys.stderr.flush()
        
