import os
import subprocess
import httpx
import asyncio
import time
from datetime import timedelta
from django.conf import settings
from django.db import models
from organism.sandbox import ensure_sandboxed

async def broadcast_status_event(type, content):
    """Utility to broadcast events to the UI."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send("rad_comm", {"type": type, **content})

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

async def add_task(title, priority="medium", description="", created_by="rad", scheduled_for=None, is_recurring=False, recurrence_interval="none"):
    """
    Assigns a new mission to Rad's backlog. 
    Args: title (str), priority (str: high/medium/low), is_recurring (bool), recurrence_interval (str: daily/weekly/monthly)
    """
    from .models import RadTask
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    # Parse scheduled_for if provided as string
    sched_dt = None
    if scheduled_for:
        if isinstance(scheduled_for, str):
            sched_dt = parse_datetime(scheduled_for)
        else:
            sched_dt = scheduled_for

    task = await RadTask.objects.acreate(
        title=title,
        priority=priority,
        description=description,
        created_by=created_by,
        scheduled_for=sched_dt,
        is_recurring=is_recurring,
        recurrence_interval=recurrence_interval
    )
    return f"NEW MISSION REGISTERED: '{task.title}' [ID: {task.id}]. Priority: {task.priority}. Recurring: {task.is_recurring}"

async def list_tasks():
    """Lists all active and completed tasks with status icons."""
    from .models import RadTask
    tasks = RadTask.objects.all().order_by('-priority', 'created_at')
    count = await tasks.acount()
    if count == 0:
        return "BACKLOG EMPTY: No active missions."
    
    res = "--- RAD MISSION LOG ---\n"
    async for t in tasks:
        status_icon = "✅" if t.status == 'done' else ("⏳" if t.status == 'doing' else "📌")
        recurring_icon = " 🔄" if t.is_recurring else ""
        creator_tag = " [BY SAWAN]" if t.created_by == 'sawan' else ""
        sched_tag = f" (Next: {t.scheduled_for.strftime('%Y-%m-%d %H:%M')})" if t.scheduled_for else ""
        res += f"{status_icon}{recurring_icon} [{t.priority.upper()}]{creator_tag} {t.title} - {t.status}{sched_tag}\n"
    return res

async def update_task(task_id_or_title, title=None, priority=None, description=None, status=None, scheduled_for=None, created_by=None):
    """
    Updates an existing task's fields.
    Args: task_id_or_title (str), title (str, optional), priority (str, optional), description (str, optional), status (str, optional), scheduled_for (str, optional), created_by (str, optional)
    """
    from .models import RadTask
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone

    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."

    changed = []
    if title is not None:
        task.title = title
        changed.append("title")
    if priority is not None:
        task.priority = priority
        changed.append("priority")
    if description is not None:
        task.description = description
        changed.append("description")
    if status is not None:
        task.status = status
        if status == 'done':
            task.completed_at = timezone.now()
            task.reward_earned = True
        changed.append("status")
    if scheduled_for is not None:
        task.scheduled_for = parse_datetime(scheduled_for)
        changed.append("scheduled_for")
    if created_by is not None:
        task.created_by = created_by
        changed.append("created_by")

    await task.asave()
    return f"MISSION UPDATED: '{task.title}' fields modified: {', '.join(changed)}."

async def complete_task(task_id_or_title):
    """
    Marks a task as completed. If recurring, schedules the next cycle.
    Args: task_id_or_title (str)
    """
    from .models import RadTask
    from django.utils import timezone
    
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    
    if task.is_recurring:
        now = timezone.now()
        if task.recurrence_interval == 'daily':
            task.scheduled_for = now + timedelta(days=1)
        elif task.recurrence_interval == 'weekly':
            task.scheduled_for = now + timedelta(weeks=1)
        elif task.recurrence_interval == 'monthly':
            task.scheduled_for = now + timedelta(days=30)
        
        task.status = 'todo'
        task.completed_at = now
        await task.asave()
        await broadcast_status_event("task_update_event", {})
        return f"RECURRING MISSION RESET: '{task.title}' rescheduled for {task.scheduled_for.strftime('%Y-%m-%d %H:%M')}."
    else:
        task.status = 'done'
        task.completed_at = timezone.now()
        task.reward_earned = True
        await task.asave()
        await broadcast_status_event("task_update_event", {})
        return f"MISSION ACCOMPLISHED: '{task.title}' is finalized."

async def delete_task(task_id_or_title):
    """
    Permanently deletes a single task from the backlog.
    Args: task_id_or_title (str)
    """
    from .models import RadTask
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    
    await task.adelete()
    return f"MISSION PURGED: '{task_id_or_title}' has been permanently deleted from the backlog."

async def delete_all_tasks():
    """
    Permanently clears the entire task backlog.
    Args: None
    """
    from .models import RadTask
    count, _ = await RadTask.objects.all().adelete()
    return f"PURGE COMPLETE: All {count} missions have been permanently erased from the backlog."

def switch_brain(model_id=None, brain=None):
    """
    Allows Rad to autonomously switch his active AI model. 
    Args: model_id (str)
    """
    target = model_id or brain
    if not target:
        return "ERROR: No model specified."
    return f"BRAIN_SHIFT: {target}"

async def save_to_vault(title, content, category="research", use_db=True):
    """
    Saves research, blueprints, or milestones. Defaults to Database for better searchability.
    Args: title (str), content (str), category (str), use_db (bool)
    """
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
    """
    Searches Rad's long-term database memories.
    Args: query (str), category (str)
    """
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
    """
    Retrieves facts about Sawan from long-term memory. Use this when you need context about Sawan.
    Args: query (str)
    """
    from .models import SawanFact
    queryset = SawanFact.objects.all().order_by('-timestamp')
    if query:
        queryset = queryset.filter(models.Q(fact__icontains=query) | models.Q(context__icontains=query))
    
    results = []
    async for item in queryset[:20]:
        results.append(f"- {item.fact} (Context: {item.context})")
    
    return "\n".join(results) if results else "No facts found in memory."

async def remember(fact, context="Direct interaction"):
    """
    Imprints a new fact or preference into Rad's long-term memory about Sawan or his environment.
    Args: fact (str), context (str)
    """
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

async def generate_image(prompt, model="flux"):
    """
    Generates a stunning image based on the prompt. 
    Args: prompt (str), model (str: 'flux', 'flux-pro', 'turbo', 'dall-e-3', 'grok-imagine')
    Returns: The URL of the generated image.
    """
    from urllib.parse import quote
    encoded_prompt = quote(prompt)
    url = f"https://gen.pollinations.ai/image/{encoded_prompt}?model={model}&seed={int(time.time())}&width=1024&height=1024&nologo=true"
    return f"IMAGE GENERATED: ![{prompt}]({url})"

async def generate_media(prompt, type="audio", model=None):
    """
    Generates audio or video based on the prompt.
    Args: prompt (str), type (str: 'audio' or 'video'), model (str, optional)
    """
    from urllib.parse import quote
    encoded_prompt = quote(prompt)
    if type == "audio":
        selected_model = model or "nova"
        url = f"https://gen.pollinations.ai/audio/{encoded_prompt}?model={selected_model}"
        return f"AUDIO GENERATED: Listen here: {url}"
    else:
        selected_model = model or "p-video"
        url = f"https://gen.pollinations.ai/video/{encoded_prompt}?model={selected_model}"
        return f"VIDEO GENERATED: Watch here: {url}"

async def get_generation_capabilities():
    """
    Returns the list of available models for image, audio, and video generation.
    """
    return {
        "image_models": ["flux", "flux-pro", "turbo", "dall-e-3", "grok-imagine", "p-image", "qwen-image", "klein", "nova-canvas"],
        "audio_models": ["nova", "elevenlabs", "acestep", "qwen-tts", "elevenmusic"],
        "video_models": ["p-video", "grok-video-pro", "ltx-2", "nova-reel"]
    }

async def diagnose_errors(limit=5):
    """
    Retrieves the most recent system errors and stack traces.
    Use this to identify bugs in your own code and fix them.
    """
    from .models import NeuralError
    from asgiref.sync import sync_to_async
    
    errors = await sync_to_async(list)(NeuralError.objects.filter(is_fixed=False)[:limit])
    if not errors:
        return "System Health: 100%. No active neural glitches detected."
    
    report = "SYSTEM DIAGNOSIS REPORT:\n"
    for err in errors:
        report += f"--- ERROR [{err.id}] ---\n"
        report += f"Type: {err.error_type}\n"
        report += f"Message: {err.message}\n"
        report += f"Timestamp: {err.timestamp}\n"
        report += f"Stack Trace Snippet:\n{err.stack_trace[-500:]}\n\n"
    
    return report

async def initiate_self_healing(error_id, fix_notes):
    """
    Marks a diagnosed error as 'Fixed' in the database.
    Use this AFTER you have successfully modified the code to fix a bug.
    Args: error_id (int), fix_notes (str)
    """
    from .models import NeuralError
    from asgiref.sync import sync_to_async
    
    try:
        err = await sync_to_async(NeuralError.objects.get)(id=error_id)
        err.is_fixed = True
        err.fix_notes = fix_notes
        await sync_to_async(err.save)()
        return f"HEALING COMPLETE: Neural Glitch [{error_id}] has been resolved and archived. Fix Notes: {fix_notes}"
    except Exception as e:
        return f"Healing Error: Could not archive glitch [{error_id}]. {str(e)}"

# Mapping tool names to functions
TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command,
    "list_dir": list_dir,
    "add_task": add_task,
    "list_tasks": list_tasks,
    "update_task": update_task,
    "complete_task": complete_task,
    "delete_task": delete_task,
    "delete_all_tasks": delete_all_tasks,
    "switch_brain": switch_brain,
    "save_to_vault": save_to_vault,
    "remember": remember,
    "search_facts": search_facts,
    "query_memory": query_memory,
    "run_background_command": run_background_command,
    "search_web": search_web,
    "modify_code": modify_code,
    "generate_image": generate_image,
    "generate_media": generate_media,
    "get_generation_capabilities": get_generation_capabilities,
    "diagnose_errors": diagnose_errors,
    "initiate_self_healing": initiate_self_healing
}
