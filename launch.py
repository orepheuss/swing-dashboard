"""
One-click launcher for the swing dashboard.

Installs any missing libraries, starts the dashboard, and opens it in your
browser. Double-click "Start Swing Dashboard.bat" (Windows) or run this file.
Keep swing_live.py and swing_scanner.py in the same folder as this file.
"""
import importlib.util
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

START_PORT = 8501
HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGES = {"streamlit": "streamlit", "plotly": "plotly", "yfinance": "yfinance",
            "pandas": "pandas", "numpy": "numpy"}


def ensure_packages():
    missing = [pkg for mod, pkg in PACKAGES.items() if importlib.util.find_spec(mod) is None]
    if missing:
        print("Installing missing libraries (first run only):", ", ".join(missing))
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def free_port(start=START_PORT, tries=30):
    """First port from 8501 upwards that nothing else is using."""
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:  # nothing is listening there
                return port
    sys.exit("Could not find a free port. Restart your computer and try again.")


def open_browser(port):
    time.sleep(5)
    webbrowser.open(f"http://localhost:{port}")


def main():
    for needed in ("swing_live.py", "swing_scanner.py"):
        if not os.path.exists(os.path.join(HERE, needed)):
            sys.exit(f"Missing {needed}. Put it in the same folder as launch.py: {HERE}")
    ensure_packages()
    port = free_port()
    if port != START_PORT:
        print(f"Port {START_PORT} is busy (an older dashboard may still be running), using {port} instead.")
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    print(f"Starting dashboard at http://localhost:{port}  (close this window or press Ctrl+C to stop)")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "swing_live.py",
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=HERE,
    )


if __name__ == "__main__":
    main()
