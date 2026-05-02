import httpx
import asyncio
import re
import html
import os
import sys
from django.conf import settings

async def search_web(query):
    """Searches the internet via DuckDuckGo."""
    print(f"[#] SEARCHING WEB: {query}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"https://api.duckduckgo.com/?q={query}&format=json")
            data = resp.json()
            abstract = data.get('AbstractText', '')
            return f"SEARCH RESULT for '{query}': {abstract}" if abstract else "Search complete, no abstract."
        except Exception as e:
            return f"SEARCH ERROR: {str(e)}"

async def browse_url(url: str, max_chars: int = 8000) -> str:
    """Extracts clean text from any URL via curl."""
    from urllib.parse import urlparse
    if urlparse(url).scheme not in ('http', 'https'): return 'Error: Invalid scheme.'
    try:
        proc = await asyncio.create_subprocess_exec('curl', '-s', '-L', '--max-time', '15', url, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        if proc.returncode != 0: return f'Fetch error: {stderr.decode()[:200]}'
        raw = stdout.decode('utf-8', errors='ignore')
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return f'=== CONTENT FROM {url} ===\n{text[:max_chars]}'
    except Exception as e: return f'Browse error: {str(e)}'

async def chrome_drive(action: str, payload: str = "", timeout: int = 45) -> str:
    """
    Advanced Chrome puppeteer for macOS. Controls the visible browser.
    Actions: search (uses Google), navigate (direct URL), fetch (extracts text), diagnose.
    """
    controller_path = os.path.join(settings.BASE_DIR, "organism", "vault", "chrome_controller.py")
    if not os.path.exists(controller_path):
        return "ERROR: Neural prosthetic (chrome_controller.py) not found in vault."

    cmd = [sys.executable, controller_path]
    if action == "diagnose":
        cmd.append("--diagnose")
    elif action in ("search", "navigate", "fetch"):
        cmd.append(payload)
    else:
        return f"ERROR: Unsupported action: {action}. Use: search, navigate, fetch, or diagnose."

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            return f"CHROME ERROR: {stderr.decode().strip()}"
        
        return f"CHROME {action.upper()} SUCCESS:\n{stdout.decode().strip()}"
    except Exception as e:
        return f"CHROME SYSTEM ERROR: {str(e)}"

async def check_internet() -> bool:
    """Checks if internet is available."""
    try:
        async with httpx.AsyncClient() as client:
            await client.get("https://www.google.com", timeout=5.0)
            return True
    except Exception:
        return False
