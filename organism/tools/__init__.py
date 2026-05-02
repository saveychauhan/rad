from .fs import read_file, write_file, list_dir
from .system import execute_command, run_background_command, stop_task, hibernate
from .missions import add_task, list_tasks, update_task, complete_task, delete_task, delete_all_tasks
from .neural import switch_brain, get_generation_capabilities, diagnose_errors, initiate_self_healing, evolve_toolkit
from .memory import save_to_vault, remember, search_facts, query_memory
from .web import search_web, browse_url, chrome_drive, check_internet
from .manifestation import generate_image, generate_media
from .code import modify_code

TOOL_MAP = {
    # --- File System (fs.py) ---
    "read_file": read_file,                 # Reads sandboxed file content
    "write_file": write_file,               # Writes/creates sandboxed files
    "list_dir": list_dir,                   # Lists directory contents

    # --- Mission Control (missions.py) ---
    "add_task": add_task,                   # Adds a new mission to the backlog
    "list_tasks": list_tasks,               # Views all active/completed missions
    "update_task": update_task,             # Modifies mission details/status
    "complete_task": complete_task,         # Finalizes a mission (handles recurring)
    "delete_task": delete_task,             # Removes a single mission
    "delete_all_tasks": delete_all_tasks,   # Clears the entire mission backlog

    # --- System & Power (system.py) ---
    "execute_command": execute_command,     # Runs shell commands (30s timeout)
    "run_background_command": run_background_command, # Offloads long tasks to Celery
    "stop_task": stop_task,                 # Kills a background process by PID
    "hibernate": hibernate,                 # Remote emergency system shutdown

    # --- Neural & Evolution (neural.py) ---
    "switch_brain": switch_brain,           # Autonomously shifts active AI model
    "get_generation_capabilities": get_generation_capabilities, # Lists media engines
    "diagnose_errors": diagnose_errors,     # Analyzes system logs for healing
    "initiate_self_healing": initiate_self_healing, # Fixes diagnosed neural glitches
    "evolve_toolkit": evolve_toolkit,       # Invents and installs new tools

    # --- Memory & Vault (memory.py) ---
    "save_to_vault": save_to_vault,         # Archives research/blueprints to Vault/DB
    "remember": remember,                   # Imprints a fact about the Creator (Sawan)
    "search_facts": search_facts,           # Retrieves learned facts about Sawan
    "query_memory": query_memory,           # Searches long-term research database

    # --- Web & Research (web.py) ---
    "search_web": search_web,               # Fast DuckDuckGo search
    "browse_url": browse_url,               # Scrapes clean text from any URL
    "chrome_drive": chrome_drive,           # GUI Chrome puppeteer for macOS

    # --- Manifestation (manifestation.py) ---
    "generate_image": generate_image,       # Generates images (Flux/Dall-E)
    "generate_media": generate_media,       # Generates Audio/Video assets

    # --- Codebase (code.py) ---
    "modify_code": modify_code              # Directly patches .py and .html files
}
