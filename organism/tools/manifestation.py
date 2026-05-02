import time
from urllib.parse import quote

async def generate_image(prompt, model="flux"):
    """Generates an image via Pollinations."""
    url = f"https://gen.pollinations.ai/image/{quote(prompt)}?model={model}&seed={int(time.time())}&nologo=true"
    return f"IMAGE GENERATED: ![{prompt}]({url})"

async def generate_media(prompt, type="audio", model=None):
    """Generates audio or video."""
    ep = "audio" if type == "audio" else "video"
    m = model or ("nova" if type == "audio" else "p-video")
    return f"{type.upper()} GENERATED: https://gen.pollinations.ai/{ep}/{quote(prompt)}?model={m}"
