import time
from urllib.parse import quote

async def generate_image(prompt, model="flux"):
    """
    Generates a high-fidelity image. 
    Models: flux (default), flux-realism, flux-anime, flux-3d, flux-pixel, any-dark.
    """
    # Normalize model name
    valid_models = ["flux", "flux-realism", "flux-anime", "flux-3d", "flux-pixel", "any-dark", "sana"]
    target_model = model if model in valid_models else "flux"
    
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?model={target_model}&seed={int(time.time())}&nologo=true&enhance=true"
    return f"IMAGE GENERATED (Model: {target_model}): ![{prompt}]({url})"

async def generate_media(prompt, type="audio", model=None):
    """Generates audio or video."""
    ep = "audio" if type == "audio" else "video"
    m = model or ("nova" if type == "audio" else "p-video")
    return f"{type.upper()} GENERATED: https://gen.pollinations.ai/{ep}/{quote(prompt)}?model={m}"
