#!/usr/bin/env python3
"""
Rad's Chrome Search Tool
Headless Chrome/Chromium fetch + fallback curl.
Extracts readable snippets without heavy deps.
"""
import sys, subprocess, os, urllib.parse, platform, re

def find_chrome():
    system = platform.system()
    candidates = []
    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        candidates = ["google-chrome", "chromium", "chromium-browser", "chrome"]
    for c in candidates:
        if os.path.exists(c):
            return c
        if subprocess.run(["which", c], capture_output=True).returncode == 0:
            return c
    return None

def fetch(url):
    chrome = find_chrome()
    if chrome:
        cmd = [chrome, "--headless", "--disable-gpu", "--disable-software-rasterizer",
               "--disable-dev-shm-usage", "--no-sandbox", "--dump-dom", url]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout
        except Exception as e:
            print(f"[!] Chrome failed: {e}", file=sys.stderr)
    # Fallback curl with Chrome UA
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    try:
        r = subprocess.run(["curl", "-s", "-L", "-A", ua, "--max-time", "20", url],
                           capture_output=True, text=True, timeout=25)
        if r.returncode == 0:
            return r.stdout
    except Exception as e:
        print(f"[!] Curl failed: {e}", file=sys.stderr)
    return ""

def extract_snippets(html):
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S|re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S|re.I)
    snippets = []
    for pattern in [
        r'<a[^>]+class="result__a"[^>]*>(.*?)</a>',
        r'<h3[^>]*>(.*?)</h3>',
        r'<span[^>]*class="st"[^>]*>(.*?)</span>',
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>',
        r'<div[^>]+class="result__snippet"[^>]*>(.*?)</div>',
        r'<p[^>]*>(.*?)</p>',
    ]:
        finds = re.findall(pattern, text, re.S|re.I)
        for f in finds[:8]:
            clean = re.sub(r'<[^>]+>', '', f)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if clean and clean not in snippets:
                snippets.append(clean)
        if snippets:
            break
    if not snippets:
        body = re.sub(r'<[^>]+>', ' ', text)
        body = re.sub(r'\s+', ' ', body).strip()
        if len(body) > 100:
            snippets = [body[:2000]]
    return "\n".join(f"• {s}" for s in snippets[:8])

SEARCH_ENGINES = [
    ("html_ddg", "https://html.duckduckgo.com/html/?q={q}"),
    ("bing", "https://www.bing.com/search?q={q}"),
    ("brave", "https://search.brave.com/search?q={q}"),
    ("searx", "https://search.sapti.me/search?q={q}"),
    ("lite_ddg", "https://lite.duckduckgo.com/lite/?q={q}"),
]

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 chrome_search.py <query>")
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    print(f"[Rad] Query: {query}")
    for name, tmpl in SEARCH_ENGINES:
        url = tmpl.format(q=urllib.parse.quote_plus(query))
        print(f"[Rad] Trying {name}...", file=sys.stderr)
        html = fetch(url)
        if not html:
            continue
        snippets = extract_snippets(html)
        if snippets and "CAPTCHA" not in snippets.upper() and "challenge" not in snippets.lower() and "duck" not in snippets.lower():
            print(snippets)
            return
    print("[X] All engines blocked or empty.")

if __name__ == "__main__":
    main()
