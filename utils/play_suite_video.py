import os
import platform
import subprocess
import webbrowser

# Adjust filename if you used a fixed name
video_file = os.path.abspath("reports/videos/50a8f98fd65b7540af1aa28651d350f6.webm")

if not os.path.exists(video_file):
    print(f"[WARN] Video file not found: {video_file}")
else:
    print(f"[INFO] Opening video: {video_file}")

    # Option 1: Open in default browser
    webbrowser.open(video_file)

    # Option 2: Open in default media player
    system = platform.system()
    if system == "Windows":
        os.startfile(video_file)
    elif system == "Darwin":  # macOS
        subprocess.call(["open", video_file])
    else:  # Linux
        subprocess.call(["xdg-open", video_file])
