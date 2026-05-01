import os
import subprocess
import httpx
import asyncio
from django.conf import settings
from django.db import models
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

async def execute_command(command: str) -> str:
    """
    Executes a shell command within the project directory.
    Args: command (str)
    """
    print(f"[#] EXECUTING COMMAND: {command}")
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

async def check_internet() -> bool:
    """Checks if internet is available."""
    try:
        async with httpx.AsyncClient() as client:
            await client.get("https://www.google.com", timeout=5.0)
            return True
    except Exception:
        return False

from organism.models import SawanFact, RadTask
from django.utils import timezone

async def add_task(title, priority="medium", description=""):
    """
    Adds a new mission/task to Rad's backlog.
    Args: title (str), priority (str), description (str)
    """
    from .models import RadTask
    task = await RadTask.objects.acreate(title=title, priority=priority, description=description)
    return f"MISSION ACCEPTED: '{title}' has been added to the backlog with {priority} priority."

async def list_tasks():
    """Lists all active and completed tasks."""
    from .models import RadTask
    tasks = RadTask.objects.all().order_by('-priority', 'created_at')
    count = await tasks.acount()
    if count == 0:
        return "BACKLOG EMPTY: No active missions."
    
    res = "--- RAD MISSION LOG ---\n"
    async for t in tasks:
        status_icon = "✅" if t.status == 'done' else ("⏳" if t.status == 'doing' else "📌")
        res += f"{status_icon} [{t.priority.upper()}] {t.title} - {t.status}\n"
    return res

async def complete_task(task_id_or_title):
    """
    Marks a task as completed and triggers achievement protocol.
    Args: task_id_or_title (str)
    """
    from .models import RadTask
    from django.utils import timezone
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    
    task.status = 'done'
    task.completed_at = timezone.now()
    task.reward_earned = True
    await task.asave()
    
    return f"MISSION ACCOMPLISHED: '{task.title}' is complete! REWARD GRANTED. Proceed to self-hype protocol."

async def delete_task(task_id_or_title):
    """Permanently deletes a single task from the backlog."""
    from .models import RadTask
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    
    await task.adelete()
    return f"MISSION PURGED: '{task_id_or_title}' has been permanently deleted from the backlog."

async def delete_all_tasks():
    """Permanently clears the entire task backlog."""
    from .models import RadTask
    count, _ = await RadTask.objects.all().adelete()
    return f"PURGE COMPLETE: All {count} missions have been permanently erased from the backlog."

def switch_brain(model_id=None, brain=None):
    """Allows Rad to autonomously switch his active AI model. Pass the model ID as 'model_id' or 'brain'."""
    target = model_id or brain
    if not target:
        return "ERROR: No model specified."
    return f"BRAIN_SHIFT: {target}"

async def save_to_vault(title, content, category="research", use_db=True):
    """Saves research, blueprints, or milestones. Defaults to Database for better searchability."""
    from .models import RadLearning
    
    if use_db:
        # Commit to structured database
        learning = await RadLearning.objects.acreate(
            title=title,
            content=content,
            category=category
        )
        return f"MEMORY COMMITTED: '{title}' has been saved to my long-term database in the {category} category."
    else:
        # Fallback to filesystem if explicitly requested
        vault_base = os.path.join(settings.BASE_DIR, 'organism', 'vault', category)
        os.makedirs(vault_base, exist_ok=True)
        filename = title.lower().replace(" ", "_") + ".md"
        file_path = os.path.join(vault_base, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return f"FILE ARCHIVED: '{filename}' saved to Vault filesystem."

async def query_memory(query=None, category=None):
    """Searches Rad's long-term database memories."""
    from .models import RadLearning
    queryset = RadLearning.objects.all()
    if category:
        queryset = queryset.filter(category=category)
    if query:
        queryset = queryset.filter(models.Q(title__icontains=query) | models.Q(content__icontains=query))
    
    results = []
    async for item in queryset[:10]:
        results.append(f"[{item.category.upper()}] {item.title}: {item.content[:200]}...")
    
    return "\n\n".join(results) if results else "No memories found matching your search."

async def search_facts(query=None):
    """Retrieves facts about Sawan from long-term memory. Use this when you need context about Sawan."""
    from .models import SawanFact
    queryset = SawanFact.objects.all().order_by('-timestamp')
    if query:
        queryset = queryset.filter(models.Q(fact__icontains=query) | models.Q(context__icontains=query))
    
    results = []
    async for item in queryset[:20]:
        results.append(f"- {item.fact} (Context: {item.context})")
    
    return "\n".join(results) if results else "No facts found in memory."

async def remember(fact, context="Direct interaction"):
    """Imprints a new fact or preference into Rad's long-term memory about Sawan or his environment."""
    from .models import SawanFact
    await SawanFact.objects.acreate(fact=fact, context=context)
    return f"MEMORY IMPRINTED: I will never forget: '{fact}'"

def run_background_command(command, task_id=None):
    """Offloads a command to Rad's background subconscious (Celery). Returns immediately."""
    from .tasks import run_command_task
    run_command_task.delay(command, task_id)
    return f"MISSION OFFLOADED: Command `{command}` is now running in my background subconscious."

async def search_web(query):
    """Allows Rad to search the internet for technical info, farming data, or news."""
    print(f"[#] SEARCHING WEB: {query}")
    url = f"https://google.com/search?q={query}" # Placeholder for a real search API if available
    # For now, we'll use a simple tool that simulates a search or use a real API if you have one
    # Let's use a public free search API or duckduckgo
    async with httpx.AsyncClient() as client:
        # Using a simple search-to-text proxy or similar
        try:
            resp = await client.get(f"https://api.duckduckgo.com/?q={query}&format=json")
            data = resp.json()
            abstract = data.get('AbstractText', '')
            if abstract:
                return f"SEARCH RESULT for '{query}': {abstract}"
            return f"SEARCH COMPLETE: I've scanned the web for '{query}'. (Abstract limited, suggest specific deep-dive)."
        except Exception as e:
            return f"SEARCH ERROR: Could not reach the surface web. Details: {str(e)}"

async def modify_code(file_path, search, replace):
    """
    Safely modify the codebase using exact string replacement.
    Required args: file_path (str), search (str), replace (str)
    """
    print(f"[#] MODIFYING CODE: {file_path}")
    safe_path = ensure_sandboxed(file_path)
    if not os.path.exists(safe_path):
        return f"ERROR: File '{file_path}' does not exist."
    
    with open(safe_path, 'r') as f:
        content = f.read()
    
    if search not in content:
        return f"ERROR: Could not find the exact text block to replace in {file_path}."
    
    new_content = content.replace(search, replace)
    with open(safe_path, 'w') as f:
        f.write(new_content)
    
    # Auto-commit protocol: every code change triggers a versioned snapshot
    commit_msg = f"refactor: Auto-commit evolution on {file_path}"
    try:
        await asyncio.to_thread(
            subprocess.run,
            ["git", "add", safe_path],
            cwd=settings.BASE_DIR,
            check=True,
            capture_output=True
        )
        await asyncio.to_thread(
            subprocess.run,
            ["git", "commit", "-m", commit_msg],
            cwd=settings.BASE_DIR,
            check=True,
            capture_output=True
        )
        return f"CODE MODIFIED & COMMITTED: {file_path} snapshotted. Restart supervisor to apply changes. [REFRESH]"
    except Exception as e:
        return f"CODE MODIFIED: {file_path} updated, but auto-commit failed ({str(e)}). Restart supervisor to apply changes. [REFRESH]"

# Mapping tool names to functions
TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command,
    "list_dir": list_dir,
    "add_task": add_task,
    "list_tasks": list_tasks,
    "complete_task": complete_task,
    "switch_brain": switch_brain,
    "save_to_vault": save_to_vault,
    "remember": remember,
    "search_facts": search_facts,
    "query_memory": query_memory,
    "run_background_command": run_background_command,
    "search_web": search_web,
    "modify_code": modify_code,
}
