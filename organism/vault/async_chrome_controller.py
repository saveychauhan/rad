#!/usr/bin/env python3
"""Async Chrome Controller Tool — Promoted from chrome_controller.py.
Lightweight asyncio wrapper for GUI Chrome automation via AppleScript.
Optimized for macOS 2017 MBA (low RAM, purge-friendly).
"""
import asyncio, subprocess, json, sys
from pathlib import Path

CONTROLLER = Path(__file__).resolve().parent / "chrome_controller.py"

async def chrome_controller(action: str, payload: str = "", timeout: int = 30) -> dict:
    if not CONTROLLER.exists():
        return {"error": "Core controller missing", "status": "missing"}

    cmd = [sys.executable, str(CONTROLLER)]
    if action == "diagnose":
        cmd.append("--diagnose")
    elif action in ("search", "navigate", "fetch"):
        cmd.append(payload)
    else:
        return {"error": f"Unsupported action: {action}", "supported": ["search","navigate","diagnose","fetch"]}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        text = stdout.decode().strip()
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            data = {"raw": text}
        return {
            "action": action, "payload": payload, "data": data,
            "stderr": stderr.decode().strip(), "returncode": proc.returncode,
            "status": "ok"
        }
    except asyncio.TimeoutError:
        return {"error": "Timeout", "action": action, "status": "timeout"}
    except Exception as e:
        return {"error": str(e), "action": action, "status": "error"}
