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
        
def print_colored(text, color_ranges, default_color='white', new_line=False):
    """
    text: string to print
    color_ranges: dict mapping color -> (start, end) range, or a list of ranges
                  e.g. {'red': (0, 8), 'blue': (9, 15)}
                  e.g. {'red': [(0, 8), (12, 15)]}  # multiple ranges, same color
    default_color: color used for any letters not covered by a range
    new_line: if True, start printing on a new line
    """
    palette = {
        'black': (0, 0, 0), 'red': (255, 0, 0), 'green': (0, 255, 0),
        'yellow': (255, 255, 0), 'blue': (0, 0, 255), 'magenta': (255, 0, 255),
        'cyan': (0, 255, 255), 'white': (255, 255, 255),
    }

    def to_rgb(color):
        return palette[color] if isinstance(color, str) else color

    colors = [default_color] * len(text)

    for color, ranges in color_ranges.items():
        if isinstance(ranges, tuple) and len(ranges) == 2 and isinstance(ranges[0], int):
            ranges = [ranges]

        for start, end in ranges:
            for i in range(start, min(end, len(text))):
                colors[i] = color

    output = ""
    for ch, color in zip(text, colors):
        r, g, b = to_rgb(color)
        output += f"\033[38;2;{r};{g};{b}m{ch}"

    output += "\033[0m"

    if new_line:
        print()

    print(output)