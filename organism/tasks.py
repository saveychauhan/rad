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
            
            # --- ATTACHMENT AWARENESS ---
            # If there's an active attachment in the current turn, notify Rad of its DISK path
            current_attachment = None
            for m in history:
                 if m.get('role') == 'user' and 'content' in m and isinstance(m['content'], list):
                      for item in m['content']:
                           if item.get('type') == 'image_url':
                                current_attachment = item['image_url'].get('url')
            
            if current_attachment:
                 memory.append({
                     "role": "system", 
            # --- LOCAL TIME AWARENESS ---
            local_now = timezone.now()
            memory.append({
                "role": "system", 
                "content": f"[SYSTEM_TIME]: The current local time is {local_now.strftime('%Y-%m-%d %H:%M:%S')} ({settings.TIME_ZONE}). Use this as the definitive 'NOW' when scheduling tasks."
            })

            memory.extend(history)
            
            # 👁️ VISION CHECK: If any message in history has multimodal content, use FREE 'openai'
            has_multimodal = any(isinstance(m['content'], list) for m in history)
            if has_multimodal:
                # Use the brain's set_model to honor the Economy Shield
                agent.brain.set_model("openai") 
                await channel_layer.group_send(group_name, {
                    "type": "rad_status_event",
                    "content": "Vision detected. Activating FREE Neural Vision (openai)..."
                })
            
            full_response = ""
            current_cost = 0.0
            in_tokens = 0
            out_tokens = 0
            current_model_before = agent.brain.model

            async for chunk in agent.think(memory, stream=True):
                # 🛑 NEURAL INTERRUPTION CHECK
                if os.path.exists(os.path.join(settings.BASE_DIR, '.rad_stop_generation')):
                    os.remove(os.path.join(settings.BASE_DIR, '.rad_stop_generation'))
                    await channel_layer.group_send(group_name, {
                        "type": "rad_status_event",
                        "content": "Consciousness Halted by User."
                    })
                    break

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
                    "content": chunk,
                    "model": agent.brain.model
                })

            # Save assistant response
            await ChatMessage.objects.acreate(role="assistant", content=full_response, model=agent.brain.model)
            
            # Finalize
            await channel_layer.group_send(group_name, {
                "type": "rad_complete_event",
                "content": full_response,
                "cost": current_cost,
                "in_tokens": in_tokens,
                "out_tokens": out_tokens,
                "model": agent.brain.model
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

    try:
        asyncio.run(run_thought())
    except Exception as e:
        from .logger import log_neural_error
        log_neural_error(e, context={"task": "process_rad_thought", "message": message_content})
        # Cleanup lock on crash
        if os.path.exists(lock_path):
            os.remove(lock_path)
            
    return "Thought complete"
