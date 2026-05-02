#!/usr/bin/env python3
"""
Rad's Chrome Controller v2.1
GUI Chrome puppeteer for macOS. Uses AppleScript to drive the visible
browser instance. Falls back to headless chrome_search.py for heavy
scraping if GUI JS bridge is disabled.

⚠️  JS bridge requires: System Preferences → Security & Privacy → Privacy →
    Automation → Allow your terminal/IDE to control Google Chrome.
"""
import subprocess, time, urllib.parse, sys, os, json, re

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

def new_window():
    osascript('tell application "Google Chrome" to make new window')
    time.sleep(1.5)

def new_tab(url="about:blank"):
    ensure_chrome()
    osascript(f'tell application "Google Chrome" to make new tab at end of tabs of window 1 with properties {{URL:"{url}"}}')
    time.sleep(0.3)

def ensure_window():
    """Ensure at least one window exists before targeting it."""
    ensure_chrome()
    try:
        count = osascript('tell application "Google Chrome" to count of windows')
        if count == "0" or not count:
            new_window()
    except RuntimeError:
        new_window()

def get_window_count():
    try:
        count = osascript('tell application "Google Chrome" to count of windows')
        return int(count) if count and count.isdigit() else 0
    except RuntimeError:
        return 0

def get_tab_count(window_index=1):
    try:
        count = osascript(f'tell application "Google Chrome" to count of tabs of window {window_index}')
        return int(count) if count and count.isdigit() else 0
    except RuntimeError:
        return 0

def navigate(url: str):
    ensure_window()
    try:
        if get_tab_count() == 0:
            new_tab(url)
            return
        current = osascript('tell application "Google Chrome" to get URL of active tab of window 1')
        if current in ("about:blank", "chrome://newtab/"):
            osascript(f'tell application "Google Chrome" to set URL of active tab of window 1 to "{url}"')
        else:
            new_tab(url)
    except Exception:
        new_tab(url)

# --- JS Bridge with Permission Awareness ---

_JS_BRIDGE_OK = None

def js_bridge_available(verbose=False) -> bool:
    global _JS_BRIDGE_OK
    if _JS_BRIDGE_OK is not None and not verbose:
        return _JS_BRIDGE_OK
    try:
        osascript('tell application "Google Chrome" to execute javascript "1+1" in active tab of window 1')
        _JS_BRIDGE_OK = True
        return True
    except RuntimeError as e:
        if "Access not allowed" in str(e) or "-1723" in str(e):
            _JS_BRIDGE_OK = False
            if verbose:
                print("[!] JS bridge blocked by macOS. Grant permission: System Preferences → Security & Privacy → Privacy → Automation → check Google Chrome for your terminal/IDE.")
            return False
        raise

def run_js(script: str) -> str:
    if not js_bridge_available():
        raise RuntimeError("JS bridge unavailable. Use headless fallback or grant macOS Automation permission.")
    safe = script.replace('"', '\\"')
    return osascript(f'tell application "Google Chrome" to execute javascript "{safe}" in active tab of window 1')

def get_page_text() -> str:
    return run_js("document.body.innerText.replace(/\\s+/g,' ').trim()")

def get_page_html() -> str:
    return run_js("document.documentElement.outerHTML")

def get_page_title() -> str:
    try:
        return osascript('tell application "Google Chrome" to get title of active tab of window 1')
    except RuntimeError:
        return ""

def get_current_url() -> str:
    try:
        return osascript('tell application "Google Chrome" to get URL of active tab of window 1')
    except RuntimeError:
        return ""

def purge_tabs(keep=1):
    """Close all tabs except `keep` to reclaim RAM on 2017 MBA."""
    ensure_window()
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

def click_element(selector: str) -> bool:
    """Attempt to click an element via CSS selector. Requires JS bridge."""
    js = f"document.querySelector('{selector}')?.click() || false"
    result = run_js(js)
    return "false" not in result.lower()

def fill_input(selector: str, value: str):
    """Fill an input field by CSS selector. Requires JS bridge."""
    safe_val = value.replace("'", "\\'")
    js = f"var el=document.querySelector('{selector}'); if(el){{el.value='{safe_val}'; el.dispatchEvent(new Event('input',{{bubbles:true}}));}}"
    run_js(js)

def scroll_page(y: int = 500):
    run_js(f"window.scrollBy(0, {y})")

# --- Keyboard / Menu Automation (No JS bridge needed) ---

def press_key(key: str, modifiers=None):
    """Send keystroke to Chrome via System Events."""
    mods = ""
    if modifiers:
        mods = " using " + " ".join(modifiers)
    osascript(f'tell application "System Events" to keystroke "{key}"{mods}')

def reload_page():
    osascript('tell application "Google Chrome" to reload active tab of window 1')

def go_back():
    osascript('tell application "Google Chrome" to go back active tab of window 1')

def go_forward():
    osascript('tell application "Google Chrome" to go forward active tab of window 1')

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
    if js_bridge_available():
        return get_page_text()
    return f"[Navigated to {url}. JS bridge unavailable — cannot extract page text.]"

def screenshot_tab(filepath: str = None):
    """Use macOS screencapture of Chrome window. Requires GUI."""
    if not filepath:
        filepath = os.path.expanduser("~/Desktop/rad_screenshot.png")
    osascript('tell application "Google Chrome" to activate')
    time.sleep(0.3)
    subprocess.run(["screencapture", "-w", filepath], capture_output=True)
    return filepath

def get_links_from_page():
    """Extract all hrefs and texts from current page. Requires JS bridge."""
    js = "Array.from(document.querySelectorAll('a[href]')).map(a=>({href:a.href, text:a.innerText.trim()}))"
    result = run_js(js)
    try:
        return json.loads(result)
    except:
        return []

# --- Diagnostics ---

def diagnose():
    """Full health check of Chrome control capabilities."""
    report = {
        "chrome_running": is_chrome_running(),
        "window_count": get_window_count(),
        "tab_count": get_tab_count(),
        "js_bridge": js_bridge_available(verbose=True),
        "current_url": get_current_url(),
        "current_title": get_page_title(),
    }
    return report

# --- CLI ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chrome_controller.py <query_or_url>")
        print("       python3 chrome_controller.py --diagnose")
        print("       python3 chrome_controller.py --navigate <url>")
        sys.exit(1)
    arg = " ".join(sys.argv[1:])
    if arg == "--diagnose":
        print(json.dumps(diagnose(), indent=2, ensure_ascii=False))
    elif arg.startswith("--navigate "):
        url = arg[11:].strip()
        navigate(url)
        print(json.dumps({"status": "navigated", "url": url}, indent=2, ensure_ascii=False))
    elif arg.startswith("http"):
        print(fetch_url(arg))
    else:
        data = search(arg)
        print(json.dumps(data, indent=2, ensure_ascii=False))
