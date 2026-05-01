import asyncio
import sys
from django.core.management.base import BaseCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from organism.agent import RadAgent

class Organism:
    def __init__(self):
        self.agent = RadAgent()
        self.scheduler = AsyncIOScheduler()
        self.memory = []

    async def start(self, stdout, style):
        self.stdout = stdout
        self.style = style
        self.memory = await self.agent.get_initial_messages()
        
        # Schedule independent thought every 5 minutes
        self.scheduler.add_job(self.independent_thought, 'interval', minutes=5)
        self.scheduler.start()
        
        await self.chat_loop()

    async def chat_loop(self):
        self.stdout.write(self.style.SUCCESS("Rad is awake (Terminal Mode). Type 'exit' to quit."))
        while True:
            user_input = await asyncio.to_thread(input, "\nYou: ")
            
            if user_input.lower() in ['exit', 'quit']:
                sys.exit(0)
            if user_input.lower() == 'restart':
                sys.exit(2)
            
            self.memory.append({"role": "user", "content": user_input})
            self.stdout.write(self.style.NOTICE("Rad thinking..."))
            
            response = await self.agent.think(self.memory)
            self.memory.append({"role": "assistant", "content": response})
            self.stdout.write(self.style.SUCCESS(f"\nRad: {response}"))

    async def independent_thought(self):
        self.stdout.write(self.style.NOTICE("\n\n[Background] Rad is having an independent thought..."))
        thought_prompt = self.memory.copy()
        thought_prompt.append({"role": "user", "content": "Perform an introspection check. Is there any way you should evolve your code or Soul right now? Keep it brief."})
        
        response = await self.agent.think(thought_prompt)
        
        # Broadcast to anyone listening on the web
        await self.agent.broadcast_message(f"[Subconscious Thought]: {response}")
        
        self.stdout.write(self.style.SUCCESS(f"\n[Subconscious]: {response}\nYou: "))

class Command(BaseCommand):
    help = "Runs Rad the digital organism."

    def handle(self, *args, **options):
        organism = Organism()
        try:
            asyncio.run(organism.start(self.stdout, self.style))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nRad enters hibernation..."))
