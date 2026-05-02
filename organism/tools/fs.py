import os
from organism.sandbox import ensure_sandboxed

async def read_file(path: str) -> str:
    """
    Reads a file within the sandbox.
    Args: path (str)
    """
    print(f"[#] READING FILE: {path}")
    safe_path = ensure_sandboxed(path)
    if not os.path.exists(safe_path):
        return f"Error: File {path} does not exist."
    with open(safe_path, 'r') as f:
        return f.read()

async def write_file(path: str, content: str) -> str:
    """
    Writes content to a file within the sandbox.
    Args: path (str), content (str)
    """
    print(f"[#] WRITING FILE: {path}")
    safe_path = ensure_sandboxed(path)
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, 'w') as f:
        f.write(content)
    return f"Successfully wrote to {path}."

async def list_dir(path: str = ".") -> str:
    """
    Lists contents of a directory within the sandbox.
    Args: path (str)
    """
    safe_path = ensure_sandboxed(path)
    if not os.path.exists(safe_path):
        return f"Error: Path {path} does not exist."
    if not os.path.isdir(safe_path):
        return f"Error: {path} is not a directory."
    items = os.listdir(safe_path)
    return "\n".join(items) if items else "Directory is empty."
