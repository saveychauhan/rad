import asyncio
import sys
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from organism.brain import Brain
from organism.models import APICall, SawanFact
from organism.tools import TOOL_MAP, check_internet
import json
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum

class Organism:
    def __init__(self):
        self.brain = Brain()
        self.scheduler = AsyncIOScheduler()
        self.pollen_limit = 0.4
        self.pollen_window = 1 # hour
        prompt_path = os.path.join(settings.BASE_DIR, 'organism', 'soul.txt')
        with open(prompt_path, 'r') as f:
            system_prompt = f.read().strip()
            
        self.memory = [
            {
                "role": "system", 
                "content": system_prompt
            }
        ]

    async def log_api_call(self, prompt, cost=0.1):
        # Using Django's async ORM capabilities
        await APICall.objects.acreate(prompt=str(prompt), pollen_cost=cost)

    async def check_pollen_budget(self):
        """Checks if Rad has enough 'pollen' energy to speak."""
        one_hour_ago = timezone.now() - timedelta(hours=self.pollen_window)
        # Using sync_to_async for complex queries if needed, but simple aggregate works
        usage = await APICall.objects.filter(timestamp__gte=one_hour_ago).aaggregate(total=Sum('pollen_cost'))
        total_used = usage['total'] or 0.0
        
        if total_used >= self.pollen_limit:
            wait_msg = f"Rad is low on Pollen ({total_used:.2f}/{self.pollen_limit}). Resting to recharge..."
            self.stdout.write(self.style.WARNING(wait_msg))
            return False
        return True

    async def wait_for_pollen(self):
        """Waits until pollen budget is available."""
        while not await self.check_pollen_budget():
            await asyncio.sleep(60) # Check every minute

    async def handle_tools(self, response_text):
        """Parses response for tool calls and executes them."""
        # Simple detection of JSON blocks like: {"tool": "read_file", "args": {"path": "test.txt"}}
        try:
            if "{" in response_text and "}" in response_text:
                # Find the first { and last }
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                tool_call = json.loads(response_text[start:end])
                
                tool_name = tool_call.get("tool")
                args = tool_call.get("args", {})
                
                if tool_name in TOOL_MAP:
                    self.stdout.write(self.style.NOTICE(f"[Tool Executing] {tool_name}({args})"))
                    result = await TOOL_MAP[tool_name](**args)
                    return f"\n[Tool Result]: {result}"
        except Exception as e:
            return f"\n[Tool Error]: {str(e)}"
        return None

    async def wait_for_internet(self):
        """Sleeps until internet is available."""
        if not await check_internet():
            self.stdout.write(self.style.WARNING("Rad is hibernating (Internet unavailable)..."))
            while not await check_internet():
                await asyncio.sleep(10)
            self.stdout.write(self.style.SUCCESS("Rad is waking up (Internet restored)!"))

    async def chat_loop(self):
        self.stdout.write(self.style.SUCCESS("Rad is awake. Chat with me (type 'exit' to shut down, 'restart' to simulate upgrade):"))
        while True:
            await self.wait_for_internet()
            await self.wait_for_pollen()
            # Use asyncio to not block the scheduler while waiting for input
            user_input = await asyncio.to_thread(input, "\nYou: ")
            
            if user_input.lower() in ['exit', 'quit']:
                self.stdout.write(self.style.WARNING("Rad shutting down safely..."))
                sys.exit(0) # 0 means intentional stop
                
            if user_input.lower() == 'restart':
                self.stdout.write(self.style.WARNING("Rad restarting (e.g., after a code upgrade)..."))
                sys.exit(2) # 2 means intentional restart for supervisor
            
            self.memory.append({"role": "user", "content": user_input})
            
            print("Rad thinking...")
            await self.log_api_call(user_input)
            response = await self.brain.think(self.memory)
            
            tool_result = await self.handle_tools(response)
            if tool_result:
                response += tool_result
                # Feed the tool result back to memory
                self.memory.append({"role": "assistant", "content": response})
                # Optionally get another response from brain based on tool result
                # For now just print it.
            
            self.memory.append({"role": "assistant", "content": response})
            self.stdout.write(self.style.SUCCESS(f"\nRad: {response}"))

    async def independent_thought(self):
        """This runs in the background continuously."""
        await self.wait_for_internet()
        if not await self.check_pollen_budget():
            return # Skip if no energy
            
        self.stdout.write(self.style.NOTICE("\n\n[Background] Rad is having an independent thought..."))
        thought_prompt = self.memory.copy()
        thought_prompt.append({"role": "user", "content": "Analyze our conversation so far. What is one proactive idea or code upgrade we should build next to make you more powerful? Keep it brief."})
        
        await self.log_api_call("independent_thought")
        response = await self.brain.think(thought_prompt)
        self.stdout.write(self.style.SUCCESS(f"\n[Subconscious]: {response}\nYou: "))

    async def load_memories(self):
        # Fetch all facts about Sawan asynchronously
        try:
            facts = ""
            async for fact_obj in SawanFact.objects.all():
                facts += f"- {fact_obj.fact}\n"
            
            if facts:
                self.memory.append({
                    "role": "system",
                    "content": f"Here are things you have learned and remembered about your creator Sawan:\n{facts}"
                })
        except Exception:
            # DB might not be migrated yet
            pass

    async def start(self, stdout, style):
        self.stdout = stdout
        self.style = style
        
        await self.load_memories()
        
        # Schedule independent thought every 5 minutes
        self.scheduler.add_job(self.independent_thought, 'interval', minutes=5)
        self.scheduler.start()
        
        # Start the chat loop
        await self.chat_loop()


class Command(BaseCommand):
    help = 'Runs the autonomous digital organism'

    def handle(self, *args, **options):
        organism = Organism()
        try:
            asyncio.run(organism.start(self.stdout, self.style))
        except (KeyboardInterrupt, SystemExit) as e:
            sys.exit(e.code if hasattr(e, 'code') else 0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"CRITICAL CRASH: {e}"))
            sys.exit(1) # 1 means crash
