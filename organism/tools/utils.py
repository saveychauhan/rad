import asyncio

async def broadcast_status_event(type, content):
    """Utility to broadcast events to the UI."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send("rad_comm", {"type": type, **content})
