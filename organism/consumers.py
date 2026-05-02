import json
import os
import threading
import time
import base64
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from .agent import RadAgent
from .models import ChatMessage

_LOCK_PATH = os.path.join(settings.BASE_DIR, '.rad_busy')

def _set_busy(busy=True):
    if busy:
        with open(_LOCK_PATH, 'w') as f:
            f.write(str(time.time()))
    else:
        if os.path.exists(_LOCK_PATH):
            os.remove(_LOCK_PATH)

_set_busy(False) # Clear on start

_TEMPLATE_PATH = os.path.join(settings.BASE_DIR, 'organism', 'templates', 'organism', 'chat.html')

def _template_watcher():
    time.sleep(3)
    last_mtime = 0
    if os.path.exists(_TEMPLATE_PATH):
        last_mtime = os.path.getmtime(_TEMPLATE_PATH)
    while True:
        time.sleep(1.5)
        try:
            if not os.path.exists(_TEMPLATE_PATH):
                continue
            current = os.path.getmtime(_TEMPLATE_PATH)
            if current != last_mtime:
                last_mtime = current
                layer = get_channel_layer()
                async_to_sync(layer.group_send)(
                    "rad_comm",
                    {"type": "force_refresh_event"}
                )
                print("[WATCHER] chat.html changed -- hot reload broadcast sent.")
        except Exception as e:
            print(f"[WATCHER] Error: {e}")

_watcher_thread = threading.Thread(target=_template_watcher, daemon=True)
_watcher_thread.start()

class RadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "rad_comm"
        self.agent = RadAgent()
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Handle specialized UI commands
        if data.get('command') == 'add_task':
            from .models import RadTask
            await RadTask.objects.acreate(
                title=data.get('title'),
                priority=data.get('priority', 'medium'),
                is_recurring=data.get('is_recurring', False),
                recurrence_interval=data.get('recurrence_interval', 'none'),
                created_by=data.get('created_by', 'sawan')
            )
            await self.channel_layer.group_send(self.group_name, {"type": "task_update_event"})
            return
            
        if data.get('command') == 'stop_generation':
            with open(os.path.join(settings.BASE_DIR, '.rad_stop_generation'), 'w') as f:
                f.write(str(time.time()))
            await self.channel_layer.group_send(self.group_name, {
                "type": "rad_status_event", 
                "content": "Interrupting neural pathways..."
            })
            return

        message = data.get('message')
        attachment = data.get('attachment')
        attachment_type = data.get('attachment_type')

        if message or attachment:
            # Handle attachment storage (base64 -> file)
            attachment_url = None
            if attachment and attachment.startswith('data:'):
                try:
                    from django.core.files.base import ContentFile

                    header, b64_content = attachment.split(';base64,')
                    ext = header.split('/')[-1].split(';')[0]
                    filename = f"{uuid.uuid4()}.{ext}"
                    
                    target_dir = os.path.join(settings.MEDIA_ROOT, 'attachments')
                    os.makedirs(target_dir, exist_ok=True)
                    filepath = os.path.normpath(os.path.join(target_dir, filename))
                    
                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(b64_content))
                        f.flush()
                        os.fsync(f.fileno())
                    
                    attachment_url = f"{settings.MEDIA_URL}attachments/{filename}"
                except Exception as e:
                    print(f"[ERROR] Failed to save attachment: {e}")

            # Persist Message with attachment URL
            await ChatMessage.objects.acreate(
                role="user", 
                content=message or "", 
                attachment=attachment_url or attachment, # Fallback to original if URL not generated
                attachment_type=attachment_type
            )
            
            # Prepare History (with multimodal awareness)
            history = []
            max_hist_chars = 4000
            current_chars = 0
            async for msg in ChatMessage.objects.all().order_by('-timestamp'):
                content = msg.content
                if msg.attachment:
                    # Multimodal representation
                    if msg.attachment_type and msg.attachment_type.startswith('image/'):
                        image_data = msg.attachment
                        if msg.attachment.startswith('/media/'):
                            # Read from disk and convert to base64 for Rad
                            try:
                                # Remove leading slash
                                relative_path = msg.attachment.lstrip('/')
                                full_path = os.path.normpath(os.path.join(settings.BASE_DIR, relative_path))
                                if os.path.exists(full_path):
                                    with open(full_path, "rb") as image_file:
                                        b64_data = base64.b64encode(image_file.read()).decode('utf-8')
                                        image_data = f"data:{msg.attachment_type};base64,{b64_data}"
                            except Exception as e:
                                print(f"[ERROR] History b64 conversion failed: {e}")

                        msg_data = {
                            "role": msg.role,
                            "content": [
                                {"type": "text", "text": f"{content}\n[PERSISTENT_ATTACHMENT_PATH: {msg.attachment}]"},
                                {"type": "image_url", "image_url": {"url": image_data}}
                            ]
                        }
                    else:
                        msg_data = {"role": msg.role, "content": f"{content}\n[FILE ATTACHED: {msg.attachment_type}]"}
                else:
                    msg_data = {"role": msg.role, "content": content}

                # Approximate char count
                msg_len = len(str(msg_data))
                if current_chars + msg_len > max_hist_chars:
                    if not history: history.append(msg_data)
                    break
                history.append(msg_data)
                current_chars += msg_len

            history.reverse()

            await self.send(text_data=json.dumps({'type': 'status', 'content': 'Rad is processing in background subconscious (Celery)...'}))
            
            # Offload to Celery
            from .tasks import process_rad_thought
            process_rad_thought.delay(
                message, 
                history, 
                image_model=data.get('image_model'),
                audio_model=data.get('audio_model'),
                video_model=data.get('video_model')
            )

    async def rad_chunk_event(self, event):
        await self.send(text_data=json.dumps({'type': 'chunk', 'role': 'rad', 'content': event['content']}))

    async def rad_complete_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_complete', 
            'role': 'rad', 
            'content': event['content'],
            'cost': event.get('cost', 0),
            'in_tokens': event.get('in_tokens', 0),
            'out_tokens': event.get('out_tokens', 0)
        }))

    async def rad_broadcast(self, event):
        await self.send(text_data=json.dumps({'type': 'rad_broadcast', 'role': 'rad', 'content': event['content'], 'is_proactive': True}))

    async def brain_shift_event(self, event):
        await self.send(text_data=json.dumps({'type': 'brain_shift', 'model': event['model']}))

    async def task_update_event(self, event):
        await self.send(text_data=json.dumps({'type': 'task_update_event'}))

    async def rad_status_event(self, event):
        await self.send(text_data=json.dumps({'type': 'status', 'content': event['content']}))

    async def force_refresh_event(self, event):
        await self.send(text_data=json.dumps({'type': 'force_refresh'}))
