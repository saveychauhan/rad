import asyncio
import httpx
import json

async def main():
    payload = {
        "model": "openai",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
        "stream_options": {"include_usage": True}
    }
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", "https://gen.pollinations.ai/v1/chat/completions", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    print(line)

asyncio.run(main())
