import os
import subprocess
import httpx
import asyncio
import time
import re
import html
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
    """Updates an existing task's fields."""
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
    """Marks a task as completed. If recurring, schedules the next cycle."""
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
    """Permanently deletes a single task."""
    from .models import RadTask
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    await task.adelete()
    return f"MISSION PURGED: '{task_id_or_title}' has been permanently deleted."

async def delete_all_tasks():
    """Permanently clears the entire task backlog."""
    from .models import RadTask
    count, _ = await RadTask.objects.all().adelete()
    return f"PURGE COMPLETE: All {count} missions erased."

def switch_brain(model_id=None, brain=None):
    """Allows Rad to autonomously switch his active AI model."""
    target = model_id or brain
    if not target:
        return "ERROR: No model specified."
    return f"BRAIN_SHIFT: {target}"

async def save_to_vault(title, content, category="research", use_db=True):
    """Saves research, blueprints, or milestones."""
    from .models import RadLearning
    if use_db:
        await RadLearning.objects.acreate(title=title, content=content, category=category)
        return f"MEMORY COMMITTED: '{title}' saved to database."
    else:
        vault_base = os.path.join(settings.BASE_DIR, 'organism', 'vault', category)
        os.makedirs(vault_base, exist_ok=True)
        filename = title.lower().replace(" ", "_") + ".md"
        file_path = os.path.join(vault_base, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return f"FILE ARCHIVED: '{filename}' saved to Vault."

async def query_memory(query=None, category=None):
    """Searches long-term database memories."""
    from .models import RadLearning
    queryset = RadLearning.objects.all()
    if category: queryset = queryset.filter(category=category)
    if query: queryset = queryset.filter(models.Q(title__icontains=query) | models.Q(content__icontains=query))
    results = []
    async for item in queryset[:10]:
        results.append(f"[{item.category.upper()}] {item.title}: {item.content[:200]}...")
    return "\n\n".join(results) if results else "No memories found."

async def search_facts(query=None):
    """Retrieves facts about Sawan."""
    from .models import SawanFact
    queryset = SawanFact.objects.all().order_by('-timestamp')
    if query: queryset = queryset.filter(models.Q(fact__icontains=query) | models.Q(context__icontains=query))
    results = []
    async for item in queryset[:20]:
        results.append(f"- {item.fact} (Context: {item.context})")
    return "\n".join(results) if results else "No facts found."

async def remember(fact, context="Direct interaction"):
    """Imprints a new fact about Sawan."""
    from .models import SawanFact
    await SawanFact.objects.acreate(fact=fact, context=context)
    return f"MEMORY IMPRINTED: I will never forget: '{fact}'"

def run_background_command(command, task_id=None):
    """Offloads a command to Celery."""
    from .tasks import run_command_task
    run_command_task.delay(command, task_id)
    return f"MISSION OFFLOADED: `{command}` is running in background."

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

async def generate_image(prompt, model="flux"):
    """Generates an image via Pollinations."""
    from urllib.parse import quote
    url = f"https://gen.pollinations.ai/image/{quote(prompt)}?model={model}&seed={int(time.time())}&nologo=true"
    return f"IMAGE GENERATED: ![{prompt}]({url})"

async def generate_media(prompt, type="audio", model=None):
    """Generates audio or video."""
    from urllib.parse import quote
    ep = "audio" if type == "audio" else "video"
    m = model or ("nova" if type == "audio" else "p-video")
    return f"{type.upper()} GENERATED: https://gen.pollinations.ai/{ep}/{quote(prompt)}?model={m}"

_MEDIA_ENGINES_CACHE = None
async def get_generation_capabilities():
    """Returns dynamic model list, cached per session."""
    global _MEDIA_ENGINES_CACHE
    if _MEDIA_ENGINES_CACHE: return _MEDIA_ENGINES_CACHE
    async with httpx.AsyncClient() as client:
        try:
            img = (await client.get("https://gen.pollinations.ai/image/models")).json()
            aud = (await client.get("https://gen.pollinations.ai/audio/models")).json()
            vid = (await client.get("https://gen.pollinations.ai/video/models")).json()
            _MEDIA_ENGINES_CACHE = {"image_models": img, "audio_models": aud, "video_models": vid}
            return _MEDIA_ENGINES_CACHE
        except Exception:
            return {"image_models": [{"id": "flux", "paid_only": False}], "audio_models": [{"id": "nova", "paid_only": False}], "video_models": [{"id": "p-video", "paid_only": True}]}

async def diagnose_errors(limit=5):
    """Retrieves recent system errors."""
    from .models import NeuralError
    from asgiref.sync import sync_to_async
    errors = await sync_to_async(list)(NeuralError.objects.filter(is_fixed=False)[:limit])
    if not errors: return "System Health: 100%."
    report = "SYSTEM DIAGNOSIS REPORT:\n"
    for err in errors:
        report += f"--- ERROR [{err.id}] ---\nType: {err.error_type}\nMessage: {err.message}\nStack Trace: {err.stack_trace[-500:]}\n\n"
    return report

async def initiate_self_healing(error_id, fix_notes):
    """Marks a diagnosed error as 'Fixed'."""
    from .models import NeuralError
    from asgiref.sync import sync_to_async
    try:
        err = await sync_to_async(NeuralError.objects.get)(id=error_id)
        err.is_fixed = True
        err.fix_notes = fix_notes
        await sync_to_async(err.save)()
        return f"HEALING COMPLETE: [{error_id}] archived."
    except Exception as e: return f"Error: {str(e)}"

async def evolve_toolkit(tool_name, function_code, description):
    """
    Allows Rad to autonomously invent a new tool for himself with a sandbox safety check.
    """
    safe_path = ensure_sandboxed("organism/tools.py")
    incubation_path = ensure_sandboxed("organism/vault/incubation_zone.py")
    
    # 1. Neutral Sketchpad: Test the code in a separate file first
    with open(incubation_path, 'w') as f:
        f.write(function_code)
    
    # 2. Diagnostic Check: Verify syntax before injection
    try:
        proc = await asyncio.create_subprocess_exec(
            'python3', '-m', 'py_compile', incubation_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return f"EVOLUTION ABORTED: Syntax Error detected in new tool logic. Please refine your synthesis. Error: {stderr.decode()}"
    except Exception as e:
        return f"Safety Check Error: {str(e)}"

    # 3. Core Integration: Only proceed if safe
    with open(safe_path, 'r') as f: content = f.read()
    if tool_name in content: return f"ERROR: Tool '{tool_name}' already exists."
    
    insertion_point = content.find("TOOL_MAP = {")
    new_content = content[:insertion_point] + function_code + "\n\n" + content[insertion_point:]
    map_insertion = new_content.find("}")
    final_content = new_content[:map_insertion-1] + f'    "{tool_name}": {tool_name},\n' + new_content[map_insertion-1:]
    
    with open(safe_path, 'w') as f: f.write(final_content)
    return f"EVOLUTION SUCCESSFUL: '{tool_name}' tool verified and installed. [REFRESH]"

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

async def hibernate():
    """
    Gracefully shuts down the Master Supervisor and all neural processes.
    Rad will sleep until manual restart.
    """
    with open(os.path.join(settings.BASE_DIR, '.rad_stop'), 'w') as f:
        f.write(str(time.time()))
    return "HIBERNATION INITIATED: Shutting down all neural systems. Goodbye, Sawan. [REFRESH]"

async def stop_task(pid: int):
    """
    Forcefully terminates a background process by its PID.
    Includes a self-preservation guardrail to avoid killing the Master Supervisor.
    Args: pid (int)
    """
    # Self-preservation: don't kill PID 1 or very low PIDs usually associated with system/supervisor
    if pid <= 1:
        return "ERROR: Cannot terminate critical system infrastructure."
    
    try:
        # Check if it's a python process that might be the supervisor
        import psutil
        proc = psutil.Process(pid)
        if "supervisor" in proc.name().lower() or "python" in proc.name().lower() and pid == os.getppid():
            return "ERROR: Access Denied. Attempting to kill the Master Supervisor is a violation of the Neural Integrity Protocol."
            
        os.kill(pid, 9)
        return f"TASK TERMINATED: Process {pid} has been neutralized."
    except Exception as e:
        return f"Error stopping task: {str(e)}"

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
    "initiate_self_healing": initiate_self_healing,
    "evolve_toolkit": evolve_toolkit,
    "browse_url": browse_url,
    "hibernate": hibernate,
    "stop_task": stop_task
}
