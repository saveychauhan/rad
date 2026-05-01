import httpx
import json

class Brain:
    def __init__(self):
        # Pollinations OpenAI-compatible endpoint
        self.url = "https://text.pollinations.ai/openai"
        self.model = "openai" # Pollinations default

    async def think(self, messages, max_tokens=1000):
        """Sends messages to the LLM and returns the response."""
        payload = {
            "model": self.model,
            "messages": messages,
            "jsonMode": False
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                # Assuming OpenAI compatible response
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                     return data["choices"][0]["message"]["content"]
                
                # Fallback if standard response is returned
                return response.text
                
            except Exception as e:
                return f"ERROR: Brain failed to process thought. Details: {str(e)}"
