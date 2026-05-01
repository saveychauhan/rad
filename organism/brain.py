import httpx
import json
from django.conf import settings

class Brain:
    def __init__(self):
        # Pollinations OpenAI-compatible endpoint
        self.url = "https://text.pollinations.ai/openai"
        self.models_url = "https://gen.pollinations.ai/v1/models"
        self.model = getattr(settings, 'POLLINATIONS_MODEL', 'openai')
        self.api_key = getattr(settings, 'POLLINATIONS_API_KEY', '')
        self._free_models = []

    async def get_free_models(self):
        """Fetches available models and filters out paid ones."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.models_url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                # Only include models that are not paid_only
                # We also only want text-capable models for the brain
                self._free_models = [
                    m['id'] for m in data.get('data', []) 
                    if not m.get('paid_only', False) and 'text' in m.get('output_modalities', [])
                ]
        except Exception:
            # Fallback to a safe list if API fails
            self._free_models = ['openai', 'mistral', 'qwen-coder']
        return self._free_models

    async def think(self, messages, max_tokens=1000):
        """Sends messages to the LLM and returns the response."""
        # Ensure we have a valid free model
        free_models = await self.get_free_models()
        if self.model not in free_models:
            # If current model is paid or invalid, pick a safe one
            self.model = free_models[0] if free_models else 'openai'

        payload = {
            "model": self.model,
            "messages": messages,
            "jsonMode": False
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=headers,
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
