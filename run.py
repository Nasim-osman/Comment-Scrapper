import sys
import os
import socket
import webbrowser
import threading
import time

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def find_available_port(start_port=8000, max_attempts=20):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port

def open_browser(url):
    time.sleep(1.5)
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    
    port = find_available_port(8000)
    url = f"http://127.0.0.1:{port}"
    
    print("=" * 60)
    print("🚀 OmniScrape - Social Media Comment Extractor & Thesis Hub")
    print("=" * 60)
    print(f"📡 Web Dashboard URL: {url}")
    print("   Supported Platforms: YouTube, Reddit, Instagram, Facebook, Twitter / X")
    print("   Exports: Excel (.xlsx), CSV, JSON")
    print("=" * 60)
    print("Opening web dashboard in your default browser...\n")
    
    # Launch browser automatically in a background timer
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    # Run FastAPI app with auto-reload enabled
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="info", reload=True)
