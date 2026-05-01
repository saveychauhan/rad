import os
import subprocess
import httpx
import asyncio
from django.conf import settings
from organism.sandbox import ensure_sandboxed

async def read_file(path: str) -> str:
    """Reads a file within the sandbox."""
    safe_path = ensure_sandboxed(path)
    if not os.path.exists(safe_path):
        return f"Error: File {path} does not exist."
    with open(safe_path, 'r') as f:
        return f.read()

async def write_file(path: str, content: str) -> str:
    """Writes content to a file within the sandbox."""
    safe_path = ensure_sandboxed(path)
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, 'w') as f:
        f.write(content)
    return f"Successfully wrote to {path}."

async def execute_command(command: str) -> str:
    """Executes a shell command within the project directory."""
    # Note: This is powerful and should be used with caution even in a sandbox.
    try:
        process = await asyncio.to_thread(
            subprocess.run,
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=settings.BASE_DIR,
            timeout=30
        )
        output = process.stdout + process.stderr
        return output if output else "Command executed with no output."
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"

async def check_internet() -> bool:
    """Checks if internet is available."""
    try:
        async with httpx.AsyncClient() as client:
            await client.get("https://www.google.com", timeout=5.0)
            return True
    except Exception:
        return False

# Mapping tool names to functions
TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command,
}
