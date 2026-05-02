from .fs import read_file, write_file, list_dir
from .system import execute_command, run_background_command, stop_task, hibernate
from .missions import add_task, list_tasks, update_task, complete_task, delete_task, delete_all_tasks
from .neural import switch_brain, get_generation_capabilities, diagnose_errors, initiate_self_healing, evolve_toolkit
from .memory import save_to_vault, remember, search_facts, query_memory
from .web import search_web, browse_url, chrome_drive, check_internet
from .manifestation import generate_image, generate_media
from .code import modify_code

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
    "stop_task": stop_task,
    "chrome_drive": chrome_drive
}
