import asyncio
import os
import django
import sys

# Add current directory to path
sys.path.append(os.getcwd())

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from organism.views import agent

async def main():
    info = await agent.brain.get_model_info()
    free_models = {k: v for k, v in info.items() if not v.get('paid_only')}
    print(free_models)

if __name__ == "__main__":
    asyncio.run(main())
