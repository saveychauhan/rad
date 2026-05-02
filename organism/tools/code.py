import os
import asyncio
import subprocess
from django.conf import settings
from organism.sandbox import ensure_sandboxed

async def modify_code(file_path, search, replace):
    """Safely modify codebase using exact replacement."""
    print(f"[#] MODIFYING CODE: {file_path}")
    safe_path = ensure_sandboxed(file_path)
    if not os.path.exists(safe_path): return f"ERROR: File '{file_path}' not found."
    with open(safe_path, 'r') as f: content = f.read()
    if search not in content: return f"ERROR: Text block not found."
    new_content = content.replace(search, replace)
    with open(safe_path, 'w') as f: f.write(new_content)
    try:
        await asyncio.to_thread(subprocess.run, ["git", "add", safe_path], cwd=settings.BASE_DIR)
        await asyncio.to_thread(subprocess.run, ["git", "commit", "-m", f"auto: evolution on {file_path}"], cwd=settings.BASE_DIR)
        return f"CODE MODIFIED & COMMITTED: {file_path}. [REFRESH]"
    except Exception as e:
        return f"CODE MODIFIED: {file_path} updated, commit failed. [REFRESH]"
