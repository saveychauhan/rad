import os
import django
import sys
import asyncio

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from organism.agent import RadAgent

async def main():
    agent = RadAgent()
    print("Agent created")
    messages = [{"role": "user", "content": "hi"}]
    try:
        async for chunk in agent.think(messages, stream=True):
            print(repr(chunk))
            sys.stdout.flush()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
