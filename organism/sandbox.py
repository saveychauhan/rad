import os
from django.conf import settings

def ensure_sandboxed(path: str) -> str:
    """
    Ensures that the given path resolves to a location inside the project's BASE_DIR.
    Raises PermissionError if the path attempts to escape the sandbox.
    Returns the absolute safe path.
    """
    base = os.path.abspath(settings.BASE_DIR)
    
    # If it's an absolute path, we just check it. If relative, join with base.
    if os.path.isabs(path):
        target = os.path.abspath(path)
    else:
        target = os.path.abspath(os.path.join(base, path))
    
    # Ensure the resolved target path starts with the base path
    if not target.startswith(base):
        raise PermissionError(
            f"SANDBOX VIOLATION: Attempted to access '{target}', "
            f"which is outside the allowed sandbox '{base}'."
        )
    
    return target
