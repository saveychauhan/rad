import asyncio
import os
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from organism.brain import Brain
from organism.models import APICall, SawanFact, ChatMessage
from organism.tools import TOOL_MAP, check_internet
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class RadAgent:
    def __init__(self):
        self.brain = Brain()
        # Default to a much higher limit if a key is present, otherwise keep it safe
        default_limit = 10.0 if self.brain.api_key else 0.4
        self.pollen_limit = getattr(settings, 'RAD_POLLEN_LIMIT', default_limit)
        self.pollen_window = 1 # hour
        self.soul_path = os.path.join(settings.BASE_DIR, 'organism', 'soul.txt')

    async def broadcast_message(self, content):
        """Pushes a message to all connected WebSocket clients."""
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "rad_comm",
            {
                "type": "rad_broadcast",
                "content": content,
            }
        )

        
    def get_soul(self):
        with open(self.soul_path, 'r') as f:
            return f.read().strip()

    async def get_initial_messages(self):
        soul = self.get_soul()
        
        # Build dynamic tool list
        tool_desc = "\n--- AVAILABLE TOOLS ---\n"
        for name, func in TOOL_MAP.items():
            desc = func.__doc__ or "No description."
            tool_desc += f"- {name}: {desc}\n"
        
        system_content = f"{soul}\n{tool_desc}\n\nTo use a tool, respond with a JSON block: " + '{"tool": "name", "args": {"arg1": "val1"}}'
        
        messages = [{"role": "system", "content": system_content}]
        
        # Load memories from SawanFact
        facts = ""
        async for fact_obj in SawanFact.objects.all():
            facts += f"- {fact_obj.fact}\n"
        
        if facts:
            messages.append({
                "role": "system",
                "content": f"Here are things you have learned and remembered about your creator Sawan:\n{facts}"
            })
        return messages

    async def check_pollen_budget(self):
        one_hour_ago = timezone.now() - timedelta(hours=self.pollen_window)
        usage = await APICall.objects.filter(timestamp__gte=one_hour_ago).aaggregate(total=Sum('pollen_cost'))
        total_used = usage['total'] or 0.0
        return total_used < self.pollen_limit, total_used

    async def think(self, messages, stream=False, depth=0):
        """Processes messages through the brain with a recursion limit to prevent loops."""
        if depth > 15:
            yield "ERROR: Neural recursion limit exceeded (depth > 15). Safety brake engaged."
            return

        if not await check_internet():
            yield "ERROR: Hibernation mode active. Internet connection required."
            return
            
        allowed, used = await self.check_pollen_budget()
        if not allowed:
            yield f"ERROR: Low on Pollen energy ({used:.2f}/{self.pollen_limit}). Recharging..."
            return

        if not stream:
            response_text, cost = await self.brain.think(messages, stream=False)
            await APICall.objects.acreate(prompt=f"Model: {self.brain.model}", pollen_cost=cost)
            
            tool_result = await self.handle_tools(response_text)
            if tool_result:
                await ChatMessage.objects.acreate(role="system", content=tool_result)
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "system", "content": tool_result})
                # Recursive call with depth tracking
                async for chunk in self.think(messages, stream=False, depth=depth+1):
                    yield chunk
            else:
                yield response_text
            return
        else:
            # Streaming branch
            generator, cost = await self.brain.think(messages, stream=True)
            await APICall.objects.acreate(prompt=f"Model: {self.brain.model} (Streaming)", pollen_cost=cost)
            
            full_response = ""
            async for chunk in generator:
                full_response += chunk
                yield chunk
            
            tool_result = await self.handle_tools(full_response)
            if tool_result:
                await ChatMessage.objects.acreate(role="system", content=tool_result)
                yield f"\n\n[SYSTEM]: {tool_result}"
                
                # If a tool was called during a stream, we might need a follow-up thought
                # We do this as a non-streaming recursive follow-up for stability
                messages.append({"role": "assistant", "content": full_response})
                messages.append({"role": "system", "content": tool_result})
                async for follow_up in self.think(messages, stream=False, depth=depth+1):
                    yield f"\n\n{follow_up}"

    async def handle_tools(self, response):
        """Detects and executes tool calls in the model's response using balanced brace matching."""
        results = []
        
        # Manually find JSON blocks by counting braces
        json_blocks = []
        start = -1
        count = 0
        for i, char in enumerate(response):
            if char == '{':
                if count == 0:
                    start = i
                count += 1
            elif char == '}':
                count -= 1
                if count == 0 and start != -1:
                    json_blocks.append(response[start:i+1])
                    start = -1

        for block in json_blocks:
            try:
                tool_data = json.loads(block)
                tool_name = tool_data.get("tool")
                if not tool_name: continue
                
                args = tool_data.get("args", {})
                
                if tool_name in TOOL_MAP:
                    print(f"\n[⚡ NEURAL TOOL CALL]: {tool_name}({str(args)[:200]})")
                    func = TOOL_MAP[tool_name]
                    try:
                        if asyncio.iscoroutinefunction(func):
                            result = await func(**args)
                        else:
                            result = func(**args)
                        print(f"[✅ TOOL RESULT]: {str(result)[:200]}...")
                    except Exception as e:
                        result = f"ERROR executing tool {tool_name}: {str(e)}"
                        print(f"[❌ TOOL ERROR]: {result}")
                    
                    # Special handling for BRAIN_SHIFT
                    if isinstance(result, str) and result.startswith("BRAIN_SHIFT: "):
                        model_id = result.split(": ")[1]
                        self.brain.set_model(model_id)
                        # Notify frontend
                        channel_layer = get_channel_layer()
                        await channel_layer.group_send(
                            "rad_comm",
                            {
                                "type": "brain_shift_event",
                                "model": model_id,
                            }
                        )
                        result = f"Neural shift complete. My active brain is now: {model_id}"
                    
                    # Notify frontend for any Task related tools
                    if tool_name in ["add_task", "complete_task"]:
                        channel_layer = get_channel_layer()
                        await channel_layer.group_send(
                            "rad_comm",
                            {
                                "type": "task_update_event",
                            }
                        )
                        
                    results.append(f"Tool [{tool_name}] output: {result}")
            except Exception:
                continue
        
        return "\n".join(results) if results else None
