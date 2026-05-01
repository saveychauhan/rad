import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from .agent import RadAgent
from .models import ChatMessage

class RadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "rad_comm"
        self.agent = RadAgent()
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        
        if message:
            # 1. Save User Message
            await ChatMessage.objects.acreate(role="user", content=message)
            
            # 2. Get Context
            history = []
            window_size = getattr(settings, 'RAD_CONTEXT_WINDOW', 10)
            async for msg in ChatMessage.objects.all().order_by('-timestamp')[:window_size]:
                history.append({"role": msg.role, "content": msg.content})
            history.reverse()
            
            memory = await self.agent.get_initial_messages()
            memory.extend(history)
            
            # 3. Notify "Thinking" status
            await self.send(text_data=json.dumps({
                'type': 'status',
                'content': 'Rad is thinking...'
            }))
            
            # 4. Rad Thinks (Streaming)
            current_model_before = self.agent.brain.model
            
            full_response = ""
            async for chunk in self.agent.think(memory, stream=True):
                full_response += chunk
                await self.send(text_data=json.dumps({
                    'type': 'chunk',
                    'role': 'rad',
                    'content': chunk
                }))
            
            current_model_after = self.agent.brain.model
            
            # 5. Save Final Response to DB
            await ChatMessage.objects.acreate(role="assistant", content=full_response)
            
            # 6. Notify finalization (for UI cleanup)
            await self.send(text_data=json.dumps({
                'type': 'message_complete',
                'role': 'rad',
                'content': full_response
            }))

            # If model changed during think, notify frontend
            if current_model_before != current_model_after:
                await self.send(text_data=json.dumps({
                    'type': 'brain_shift',
                    'model': current_model_after
                }))

    # Receive message from group
    async def rad_broadcast(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'role': 'rad',
            'content': event['content'],
            'is_proactive': True
        }))

    async def brain_shift_event(self, event):
        # Send signal to WebSocket to update the dropdown
        await self.send(text_data=json.dumps({
            'type': 'brain_shift',
            'model': event['model']
        }))

    async def task_update_event(self, event):
        # Send signal to WebSocket to refresh task list
        await self.send(text_data=json.dumps({
            'type': 'task_update'
        }))
