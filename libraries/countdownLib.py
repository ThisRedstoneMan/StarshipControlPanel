def format_seconds_to_clock(signed_seconds):
        prefix = "T- " if signed_seconds < 0 else "T+ "
        abs_secs = abs(signed_seconds)
        hours = abs_secs // 3600
        minutes = (abs_secs % 3600) // 60
        seconds = abs_secs % 60
        return f"{prefix}{hours:02d} : {minutes:02d} : {seconds:02d}"