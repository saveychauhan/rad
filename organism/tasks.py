import subprocess
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json
import os
import time
from django.conf import settings

@shared_task
def run_command_task(command, task_id=None):
    """Executes a shell command in the background and updates the task status."""
    from .models import RadTask
    
    try:
        # Start the work
        if task_id:
            task = RadTask.objects.get(id=task_id)
            task.status = 'doing'
            task.save()
            
            # Notify UI
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "rad_comm",
                {"type": "task_update_event"}
            )

        # Run the command
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout + result.stderr
        
        # Finish the work
        if task_id:
            task = RadTask.objects.get(id=task_id)
            task.status = 'done'
            task.completed_at = timezone.now()
            task.reward_earned = True
            task.save()
            
            # Notify UI & Rad
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "rad_comm",
                {"type": "task_update_event"}
            )
            async_to_sync(channel_layer.group_send)(
                "rad_comm",
                {
                    "type": "rad_broadcast",
                    "content": f"[BACKGROUND MISSION COMPLETE]: Command `{command}` finished.\nOutput:\n{output[:500]}"
                }
            )
            
        return output
    except Exception as e:
        if task_id:
            task = RadTask.objects.get(id=task_id)
            task.status = 'todo' # Reset on failure
            task.save()
        return str(e)

@shared_task
def process_rad_thought(message_content, history, image_model=None, audio_model=None, video_model=None):
    """
    Offloads Rad's complex thinking and tool execution to Celery.
    Streams results back to the UI via WebSockets.
    """
    from .agent import RadAgent
    from .models import ChatMessage
    from asgiref.sync import async_to_sync
    import asyncio

    agent = RadAgent()
    channel_layer = get_channel_layer()
    group_name = "rad_comm"
    
    # Apply UI Preferences
    agent.preferred_image_model = image_model or "flux"
    agent.preferred_audio_model = audio_model or "nova"
    agent.preferred_video_model = video_model or "p-video"

    # Set busy lock
    lock_path = os.path.join(settings.BASE_DIR, '.rad_busy')
    with open(lock_path, 'w') as f:
        f.write(str(time.time()))

    async def run_thought():
        try:
            await channel_layer.group_send(group_name, {
                "type": "rad_status_event",
                "content": "Rad is synthesizing a response..."
            })
            
            # Add user message to history
            memory = await agent.get_initial_messages()
            memory.extend(history)
            
            # 👁️ VISION CHECK: If any message in history has multimodal content, use gemini-large
            has_multimodal = any(isinstance(m['content'], list) for m in history)
            if has_multimodal:
                agent.brain.model = "gemini-large"
                await channel_layer.group_send(group_name, {
                    "type": "rad_status_event",
                    "content": "Vision detected. Activating Gemini-Large..."
                })
            
            full_response = ""
            current_cost = 0.0
            in_tokens = 0
            out_tokens = 0
            current_model_before = agent.brain.model

            async for chunk in agent.think(memory, stream=True):
                if chunk.startswith("__META__:"):
                    parts = chunk.split(":")[1].split("|")
                    current_cost = float(parts[0])
                    if len(parts) > 2:
                        in_tokens = int(parts[1])
                        out_tokens = int(parts[2])
                    continue
                if chunk.startswith("__COST__:"):
                    current_cost = float(chunk.split(":")[1])
                    continue
                
                full_response += chunk
                await channel_layer.group_send(group_name, {
                    "type": "rad_chunk_event",
                    "content": chunk
                })

            # Save assistant response
            await ChatMessage.objects.acreate(role="assistant", content=full_response)
            
            # Finalize
            await channel_layer.group_send(group_name, {
                "type": "rad_complete_event",
                "content": full_response,
                "cost": current_cost,
                "in_tokens": in_tokens,
                "out_tokens": out_tokens
            })

            current_model_after = agent.brain.model
            if current_model_before != current_model_after:
                await channel_layer.group_send(group_name, {
                    "type": "brain_shift_event",
                    "model": current_model_after
                })

        finally:
            if os.path.exists(lock_path):
                os.remove(lock_path)

    asyncio.run(run_thought())
    return "Thought complete"
