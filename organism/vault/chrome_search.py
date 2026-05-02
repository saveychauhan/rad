#!/usr/bin/env python3
"""
Rad's Chrome Search Tool v2 — Low-Resource Edition
Prioritizes curl over headless Chrome for 2017 MBA survival.
Extracts readable snippets without heavy deps.
"""
import sys, subprocess, os, urllib.parse, platform, re

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

def curl_fetch(url, timeout=15):
    try:
        r = subprocess.run(
            ["curl", "-s", "-L", "-A", UA, "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout+5
        )
        if r.returncode == 0:
            return r.stdout
    except Exception as e:
        print(f"[!] Curl failed: {e}", file=sys.stderr)
    return ""

def extract_snippets(html):
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S|re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S|re.I)
    snippets = []
    # DuckDuckGo HTML results
    for pattern in [
        r'<a[^>]+class="result__a"[^>]*>(.*?)</a>',
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        r'<div[^>]+class="result__snippet"[^>]*>(.*?)</div>',
        r'<h2[^>]*>(.*?)</h2>',
        r'<h3[^>]*>(.*?)</h3>',
        r'<p[^>]*>(.*?)</p>',
    ]:
        finds = re.findall(pattern, text, re.S|re.I)
        for f in finds[:10]:
            clean = re.sub(r'<[^>]+>', '', f)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if clean and clean not in snippets and len(clean) > 15:
                snippets.append(clean)
        if len(snippets) >= 8:
            break
    if not snippets:
        body = re.sub(r'<[^>]+>', ' ', text)
        body = re.sub(r'\s+', ' ', body).strip()
        if len(body) > 100:
            # Split into sentences/chunks
            parts = re.split(r'(?<=[.!?])\s+', body)
            for p in parts[:10]:
                p = p.strip()
                if len(p) > 30 and p not in snippets:
                    snippets.append(p)
                if len(snippets) >= 8:
                    break
    return "\n".join(f"• {s}" for s in snippets[:8])

SEARCH_ENGINES = [
    ("lite_ddg", "https://lite.duckduckgo.com/lite/?q={q}"),
    ("html_ddg", "https://html.duckduckgo.com/html/?q={q}"),
    ("bing", "https://www.bing.com/search?q={q}"),
]

def search(query):
    print(f"[Rad] Query: {query}", file=sys.stderr)
    for name, tmpl in SEARCH_ENGINES:
        url = tmpl.format(q=urllib.parse.quote_plus(query))
        print(f"[Rad] Trying {name}...", file=sys.stderr)
        html = curl_fetch(url, timeout=12)
        if not html:
            continue
        snippets = extract_snippets(html)
        if snippets:
            # Filter out captcha/challenge text
            flat = snippets.lower()
            if any(x in flat for x in ["captcha", "challenge", "verify you are human", "ip address"]):
                print(f"[!] {name} blocked by CAPTCHA. Next engine...", file=sys.stderr)
                continue
            print(snippets)
            return
    print("[X] All engines blocked or empty.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chrome_search.py <query>")
        sys.exit(1)
    search(" ".join(sys.argv[1:]))
