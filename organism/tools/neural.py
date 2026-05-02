import asyncio
import httpx
import os
from asgiref.sync import sync_to_async
from organism.sandbox import ensure_sandboxed

async def switch_brain(model_id=None, brain=None):
    """Allows Rad to autonomously switch his active AI model."""
    from .utils import broadcast_status_event
    from organism.views import agent
    
    target = model_id or brain
    if not target:
        return "ERROR: No model specified."
    
    success = agent.brain.set_model(target)
    if not success:
        return f"ECONOMY SHIELD: I cannot shift to '{target}' as it is a PAID model. I will remain on {agent.brain.model}."
    
    return f"BRAIN_SHIFT: {target}"

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
    from organism.models import NeuralError
    errors = await sync_to_async(list)(NeuralError.objects.filter(is_fixed=False)[:limit])
    if not errors: return "System Health: 100%."
    report = "SYSTEM DIAGNOSIS REPORT:\n"
    for err in errors:
        report += f"--- ERROR [{err.id}] ---\nType: {err.error_type}\nMessage: {err.message}\nStack Trace: {err.stack_trace[-500:]}\n\n"
    return report

async def initiate_self_healing(error_id, fix_notes):
    """Marks a diagnosed error as 'Fixed'."""
    from organism.models import NeuralError
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
    safe_path = ensure_sandboxed("organism/tools/__init__.py") # Now evolving the package init or a new file
    incubation_path = ensure_sandboxed("organism/vault/incubation_zone.py")
    
    with open(incubation_path, 'w') as f:
        f.write(function_code)
    
    try:
        proc = await asyncio.create_subprocess_exec(
            'python3', '-m', 'py_compile', incubation_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return f"EVOLUTION ABORTED: Syntax Error detected in new tool logic. Error: {stderr.decode()}"
    except Exception as e:
        return f"Safety Check Error: {str(e)}"

    # For modular evolution, we'll create a new file in tools/ or append to __init__
    # For now, let's keep appending to __init__ to maintain the TOOL_MAP logic
    with open(safe_path, 'r') as f: content = f.read()
    if tool_name in content: return f"ERROR: Tool '{tool_name}' already exists."
    
    insertion_point = content.find("TOOL_MAP = {")
    new_content = content[:insertion_point] + function_code + "\n\n" + content[insertion_point:]
    map_insertion = new_content.find("}")
    final_content = new_content[:map_insertion-1] + f'    "{tool_name}": {tool_name},\n' + new_content[map_insertion-1:]
    
    with open(safe_path, 'w') as f: f.write(final_content)
    return f"EVOLUTION SUCCESSFUL: '{tool_name}' tool verified and installed in modular cortex. [REFRESH]"
