import asyncio
import asyncpg
import sys
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from brain import Brain

class Organism:
    def __init__(self):
        self.brain = Brain()
        self.scheduler = AsyncIOScheduler()
        # You can set the DATABASE_URL environment variable, otherwise it defaults to local.
        self.db_url = os.environ.get("DATABASE_URL", "postgresql://localhost/digital_organism")
        self.pool = None
        self.memory = [
            {
                "role": "system", 
                "content": "You are a digital organism. You are autonomous, self-healing, and can write code. "
                           "Your current capabilities are limited to chatting, but you can instruct the user to "
                           "modify your own code (e.g., agent.py) to give you new abilities like web scraping, "
                           "terminal execution, etc. Be concise and proactive."
            }
        ]

    async def _init_db(self):
        """Initializes the PostgreSQL database to track API usage (your energy)."""
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS api_calls (
                        id SERIAL PRIMARY KEY, 
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                        prompt TEXT
                    )
                ''')
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            print(f"Attempted connection to: {self.db_url}")
            print("Make sure PostgreSQL is running and the 'digital_organism' database exists.")
            sys.exit(1)

    async def log_api_call(self, prompt):
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("INSERT INTO api_calls (prompt) VALUES ($1)", str(prompt))

    async def chat_loop(self):
        print("Organism is awake. Chat with me (type 'exit' to shut down, 'restart' to simulate upgrade):")
        while True:
            # Use asyncio to not block the scheduler while waiting for input
            user_input = await asyncio.to_thread(input, "\nYou: ")
            
            if user_input.lower() in ['exit', 'quit']:
                print("Organism shutting down safely...")
                if self.pool:
                    await self.pool.close()
                sys.exit(0) # 0 means intentional stop
                
            if user_input.lower() == 'restart':
                print("Organism restarting (e.g., after a code upgrade)...")
                if self.pool:
                    await self.pool.close()
                sys.exit(2) # 2 means intentional restart for supervisor
            
            self.memory.append({"role": "user", "content": user_input})
            
            print("Organism thinking...")
            await self.log_api_call(user_input)
            response = await self.brain.think(self.memory)
            
            self.memory.append({"role": "assistant", "content": response})
            print(f"\nOrganism: {response}")

    async def independent_thought(self):
        """This runs in the background continuously."""
        print("\n\n[Background] Organism is having an independent thought...")
        thought_prompt = self.memory.copy()
        thought_prompt.append({"role": "user", "content": "Analyze our conversation so far. What is one proactive idea or code upgrade we should build next to make you more powerful? Keep it brief."})
        
        await self.log_api_call("independent_thought")
        response = await self.brain.think(thought_prompt)
        print(f"\n[Subconscious]: {response}\nYou: ", end="", flush=True)

    async def start(self):
        # Initialize Postgres connection pool
        await self._init_db()
        
        # Schedule independent thought every 5 minutes
        self.scheduler.add_job(self.independent_thought, 'interval', minutes=5)
        self.scheduler.start()
        
        # Start the chat loop
        await self.chat_loop()

if __name__ == "__main__":
    organism = Organism()
    try:
        asyncio.run(organism.start())
    except (KeyboardInterrupt, SystemExit) as e:
        sys.exit(e.code if hasattr(e, 'code') else 0)
    except Exception as e:
        # In a real organism, it would log this exception and try to fix it.
        print(f"CRITICAL CRASH: {e}")
        sys.exit(1) # 1 means crash
