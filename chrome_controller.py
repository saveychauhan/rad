#!/usr/bin/env python3
"""
Rad's Chrome Controller
GUI Chrome puppeteer for macOS. Uses AppleScript to drive the visible
browser instance. Falls back to headless chrome_search.py for heavy
scraping if GUI JS bridge is disabled.
"""
import subprocess, time, urllib.parse, sys, os, json

# --- AppleScript Primitives ---

def osascript(cmd: str) -> str:
    r = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"AppleScript failed: {r.stderr.strip()}")
    return r.stdout.strip()

def is_chrome_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0

def ensure_chrome():
    if not is_chrome_running():
        osascript('tell application "Google Chrome" to activate')
        time.sleep(2.5)

def new_tab(url="about:blank"):
    ensure_chrome()
    osascript(f'tell application "Google Chrome" to make new tab at end of tabs of window 1 with properties {{URL:"{url}"}}')
    time.sleep(0.3)

def navigate(url: str):
    ensure_chrome()
    try:
        current = osascript('tell application "Google Chrome" to get URL of active tab of window 1')
        if current in ("about:blank", "chrome://newtab/"):
            osascript(f'tell application "Google Chrome" to set URL of active tab of window 1 to "{url}"')
        else:
            new_tab(url)
    except Exception:
        new_tab(url)

def js_bridge_available() -> bool:
    try:
        osascript('tell application "Google Chrome" to execute javascript "1+1" in active tab of window 1')
        return True
    except RuntimeError:
        return False

def run_js(script: str) -> str:
    safe = script.replace('"', '\\"')
    return osascript(f'tell application "Google Chrome" to execute javascript "{safe}" in active tab of window 1')

def get_page_text() -> str:
    js = "document.body.innerText.replace(/\\s+/g,' ').trim()"
    return run_js(js)

def purge_tabs(keep=1):
    """Close all tabs except `keep` to reclaim RAM on 2017 MBA."""
    ensure_chrome()
    script = f'''
    tell application "Google Chrome"
        set t to tabs of window 1
        repeat with i from (count of t) to 1 by -1
            if i > {keep} then close tab i of window 1
        end repeat
    end tell
    '''
    osascript(script)
    print(f"[Rad] Purged tabs. Keeping {keep}.")

# --- Search & Retrieval ---

SEARCH_TEMPLATES = {
    "google": "https://www.google.com/search?q={q}",
    "duckduckgo": "https://html.duckduckgo.com/html/?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "brave": "https://search.brave.com/search?q={q}",
}

def search(query: str, engine="duckduckgo", wait=3):
    tmpl = SEARCH_TEMPLATES.get(engine, SEARCH_TEMPLATES["duckduckgo"])
    url = tmpl.format(q=urllib.parse.quote_plus(query))
    navigate(url)
    time.sleep(wait)
    if js_bridge_available():
        text = get_page_text()
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
        return {"source": "gui", "query": query, "results": lines[:12]}
    else:
        print("[!] GUI JS bridge disabled. Falling back to headless chrome_search...")
        here = os.path.dirname(os.path.abspath(__file__))
        cp = subprocess.run([sys.executable, os.path.join(here, "chrome_search.py"), query],
                            capture_output=True, text=True)
        return {"source": "headless", "query": query, "results": cp.stdout.strip().splitlines()[:12]}

def fetch_url(url: str, wait=3):
    navigate(url)
    time.sleep(wait)
    return get_page_text()

# --- CLI ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chrome_controller.py <query_or_url>")
        sys.exit(1)
    arg = " ".join(sys.argv[1:])
    if arg.startswith("http"):
        print(fetch_url(arg))
    else:
        data = search(arg)
        print(json.dumps(data, indent=2, ensure_ascii=False))
