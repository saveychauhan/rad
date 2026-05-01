import subprocess
import time
import sys
import os
import signal

class RadSupervisor:
    def __init__(self):
        self.processes = {}
        self.is_running = True

    def start_process(self, name, command):
        print(f"[*] Starting {name}...")
        # Use shell=True to allow for venv activation if needed, 
        # though we assume sys.executable is the venv python
        return subprocess.Popen(command, stdout=None, stderr=None)

    def run(self):
        print("=== RAD MASTER SUPERVISOR STARTING ===")
        print("Initializing Conscious (Django) and Subconscious (Celery) systems...")

        # Commands to run
        # We use sys.executable to ensure we stay in the same venv
        commands = {
            "Django (UI)": [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"],
            "Celery (Subconscious)": ["celery", "-A", "core", "worker", "-l", "info"]
        }

        # Start all processes
        for name, cmd in commands.items():
            self.processes[name] = self.start_process(name, cmd)

        print("\n[!] RAD IS ALIVE. Access UI at http://127.0.0.1:8000/")
        print("[!] Press Ctrl+C to hibernate the entire organism.\n")

        try:
            while self.is_running:
                for name, process in self.processes.items():
                    # Check if process is still alive
                    if process.poll() is not None:
                        print(f"\n[CRITICAL] {name} has stopped (Exit Code: {process.returncode})")
                        print(f"[*] Attempting to resuscitate {name} in 3 seconds...")
                        time.sleep(3)
                        self.processes[name] = self.start_process(name, commands[name])
                
                time.sleep(2)
        except KeyboardInterrupt:
            self.hibernate()

    def hibernate(self):
        print("\n=== HIBERNATION SIGNAL RECEIVED ===")
        self.is_running = False
        for name, process in self.processes.items():
            print(f"[*] Stopping {name}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("=== RAD IS NOW HIBERNATING. GOODBYE. ===")

if __name__ == "__main__":
    # Ensure we are in the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    supervisor = RadSupervisor()
    supervisor.run()
