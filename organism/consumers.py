import json
import os
import threading
import time
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
        message = data.get('message')
        if message:
            _set_busy(True)
            try:
                await ChatMessage.objects.acreate(role="user", content=message)
                history = []
                max_hist_chars = 4000
                max_msg_chars = 1500
                current_chars = 0
                
                async for msg in ChatMessage.objects.all().order_by('-timestamp'):
                    content = msg.content
                    if len(content) > max_msg_chars:
                        content = content[:max_msg_chars] + "\n\n...[CONTENT TRUNCATED FOR MEMORY]..."
                    
                    if current_chars + len(content) > max_hist_chars:
                        if not history: # Always include the very last message
                            history.append({"role": msg.role, "content": content})
                        break
                        
                    history.append({"role": msg.role, "content": content})
                    current_chars += len(content)
                    
                history.reverse()
                memory = await self.agent.get_initial_messages()
                memory.extend(history)
                await self.send(text_data=json.dumps({'type': 'status', 'content': 'Rad is thinking...'}))
                current_model_before = self.agent.brain.model
                full_response = ""
                current_cost = 0.0
                in_tokens = 0
                out_tokens = 0
                async for chunk in self.agent.think(memory, stream=True):
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
                    await self.send(text_data=json.dumps({'type': 'chunk', 'role': 'rad', 'content': chunk}))
                
                current_model_after = self.agent.brain.model
                await ChatMessage.objects.acreate(role="assistant", content=full_response)
                
                # Send completion with cost and tokens
                await self.send(text_data=json.dumps({
                    'type': 'message_complete', 
                    'role': 'rad', 
                    'content': full_response,
                    'cost': current_cost,
                    'in_tokens': in_tokens,
                    'out_tokens': out_tokens
                }))
                if current_model_before != current_model_after:
                    await self.send(text_data=json.dumps({'type': 'brain_shift', 'model': current_model_after}))
            finally:
                _set_busy(False)

    async def rad_broadcast(self, event):
        await self.send(text_data=json.dumps({'type': 'rad_broadcast', 'role': 'rad', 'content': event['content'], 'is_proactive': True}))

    async def brain_shift_event(self, event):
        await self.send(text_data=json.dumps({'type': 'brain_shift', 'model': event['model']}))

    async def task_update_event(self, event):
        await self.send(text_data=json.dumps({'type': 'task_update_event'}))

    async def force_refresh_event(self, event):
        await self.send(text_data=json.dumps({'type': 'force_refresh'}))
