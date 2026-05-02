import subprocess
import asyncio
import os
import sys
import time
from django.conf import settings

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

def run_background_command(command, task_id=None):
    """Offloads a command to Celery."""
    from organism.tasks import run_command_task
    run_command_task.delay(command, task_id)
    return f"MISSION OFFLOADED: `{command}` is running in background."

async def stop_task(pid: int):
    """
    Forcefully terminates a background process by its PID.
    Includes a self-preservation guardrail to avoid killing the Master Supervisor.
    Args: pid (int)
    """
    if pid <= 1:
        return "ERROR: Cannot terminate critical system infrastructure."
    
    try:
        import psutil
        proc = psutil.Process(pid)
        if "supervisor" in proc.name().lower() or ("python" in proc.name().lower() and pid == os.getppid()):
            return "ERROR: Access Denied. Attempting to kill the Master Supervisor is a violation of the Neural Integrity Protocol."
            
        os.kill(pid, 9)
        return f"TASK TERMINATED: Process {pid} has been neutralized."
    except Exception as e:
        return f"Error stopping task: {str(e)}"

async def hibernate():
    """
    Gracefully shuts down the Master Supervisor and all neural processes.
    Rad will sleep until manual restart.
    """
    with open(os.path.join(settings.BASE_DIR, '.rad_stop'), 'w') as f:
        f.write(str(time.time()))
    return "HIBERNATION INITIATED: Shutting down all neural systems. Goodbye, Sawan. [REFRESH]"
