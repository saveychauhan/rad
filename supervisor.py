import subprocess
import time
import sys
import os
import threading

class RadSupervisor:
    def __init__(self):
        self.processes = {}
        self.is_running = True
        self.last_checksums = {}
        self.watched_paths = ['core', 'organism', 'digital_organism', 'manage.py', 'supervisor.py']
        self.reload_flag = False

    def snapshot_codebase(self):
        """Lightweight mtime snapshot. Skips venv, cache, and hidden dirs."""
        snap = {}
        for p in self.watched_paths:
            if os.path.isfile(p):
                try:
                    snap[p] = os.path.getmtime(p)
                except OSError:
                    pass
            elif os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '__pycache__', 'migrations', 'vault')]
                    for f in files:
                        if f.endswith('.py') and not f.startswith('.rad'):
                            full = os.path.join(root, f)
                            try:
                                snap[full] = os.path.getmtime(full)
                            except OSError:
                                pass
        return snap

    def auto_commit(self):
        try:
            msg = f"Auto-commit on mutation {time.strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(['git', 'add', '-A'], check=False, capture_output=True)
            res = subprocess.run(['git', 'commit', '-m', msg], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"[✅ AUTO-COMMIT] {msg}")
            elif 'nothing to commit' not in res.stderr.lower():
                print(f"[⚠️ GIT] {res.stderr.strip()}")
        except Exception as e:
            print(f"[❌ AUTO-COMMIT ERROR] {e}")

    def watcher_thread(self):
        print("[*] Watcher active. Monitoring code mutations...")
        self.last_checksums = self.snapshot_codebase()
        while self.is_running:
            time.sleep(1.5)
            current = self.snapshot_codebase()
            if current != self.last_checksums:
                # 🛡️ PROTECTIVE LOCK: Wait if Rad is still talking
                while os.path.exists('.rad_busy'):
                    # Check if the lock is stale (older than 2 mins)
                    try:
                        if time.time() - os.path.getmtime('.rad_busy') > 120:
                            print("[⚠️] AI busy lock looks stale. Breaking lock...")
                            os.remove('.rad_busy')
                            break
                    except: pass
                    
                    print("[⏳] Rad is busy communicating. Holding mutation reload...")
                    time.sleep(3)

                print("\n[🧬 MUTATION DETECTED] Auto-committing and rebooting neural processes...")
                self.auto_commit()
                self.reload_flag = True
                for name, proc in self.processes.items():
                    if proc.poll() is None:
                        print(f"[*] Stopping {name} for reload...")
                        proc.terminate()
                self.last_checksums = current

    def start_process(self, name, command):
        print(f"[*] Starting {name}...")
        return subprocess.Popen(command, stdout=None, stderr=None)

    def run(self):
        print("=== RAD MASTER SUPERVISOR STARTING ===")
        commands = {
            "Django (UI)": [sys.executable, "manage.py", "runserver", "0.0.0.0:8000", "--noreload"],
            "Celery (Subconscious)": ["celery", "-A", "core", "worker", "-l", "info"]
        }

        for name, cmd in commands.items():
            self.processes[name] = self.start_process(name, cmd)

        threading.Thread(target=self.watcher_thread, daemon=True).start()

        print("\n[!] RAD IS ALIVE. UI: http://127.0.0.1:8000/")
        print("[!] Press Ctrl+C to hibernate.\n")

        try:
            while self.is_running:
                for name, process in list(self.processes.items()):
                    if process.poll() is not None:
                        if not self.reload_flag:
                            print(f"\n[CRITICAL] {name} stopped (code {process.returncode})")
                            print(f"[*] Resuscitating in 3s...")
                            time.sleep(3)
                        else:
                            print(f"[*] Reloading {name}...")
                        
                        self.processes[name] = self.start_process(name, commands[name])
                
                if os.path.exists('.rad_stop'):
                    os.remove('.rad_stop')
                    self.hibernate()
                    return

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
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    RadSupervisor().run()
