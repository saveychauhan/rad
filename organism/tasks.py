import subprocess
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json

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
