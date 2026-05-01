import subprocess
import time
import sys

def start_organism():
    print("=== Supervisor starting organism ===")
    while True:
        try:
            # Run the agent as a subprocess
            process = subprocess.run([sys.executable, "agent.py"])
            
            # The agent controls its own lifecycle via exit codes
            if process.returncode == 0:
                print("=== Organism intentionally shut down. Exiting supervisor. ===")
                break
            elif process.returncode == 2:
                print("=== Organism requested restart (e.g. after code update). Restarting in 1s... ===")
                time.sleep(1)
            else:
                print(f"=== Organism CRASHED (Exit Code {process.returncode}). Restarting in 3s to survive... ===")
                # In a more advanced version, the supervisor would git revert here
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\nSupervisor manually stopped.")
            break
        except Exception as e:
            print(f"Supervisor critical error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_organism()
