import httpx
import json
from django.conf import settings

class Brain:
    _current_model = None

    def __init__(self):
        # Pollinations OpenAI-compatible endpoint
        self.url = "https://gen.pollinations.ai/v1/chat/completions"
        self.models_url = "https://gen.pollinations.ai/v1/models"
        self.default_model = getattr(settings, 'POLLINATIONS_MODEL', 'openai')
        
        if Brain._current_model is None:
            Brain._current_model = self.default_model
            
        self.api_key = getattr(settings, 'POLLINATIONS_API_KEY', '')
        self._free_models = []
        self._model_info = {}

    @property
    def model(self):
        return Brain._current_model

    @model.setter
    def model(self, value):
        Brain._current_model = value

    def set_model(self, model_id):
        self.model = model_id

    async def get_model_info(self):
        """Fetches models and their costs from Pollinations."""
        if self._model_info:
            return self._model_info
            
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://gen.pollinations.ai/v1/models")
                data = resp.json()
                self._model_info = {
                    m['id']: {
                        'cost': m.get('cost', 0.1),
                        'paid_only': m.get('paid_only', False)
                    }
                    for m in data.get('data', [])
                    if 'text' in m.get('output_modalities', [])
                }
        except Exception:
            # Safe fallbacks
            self._model_info = {
                'openai': {'cost': 0.1, 'paid_only': False},
                'mistral': {'cost': 0.05, 'paid_only': False},
            }
        return self._model_info

    async def get_free_models(self):
        info = await self.get_model_info()
        return [mid for mid, meta in info.items() if not meta['paid_only']]

    async def think(self, messages, stream=False):
        """Sends messages to the brain and returns the response (supports streaming)."""
        payload = {
            "model": self.model if self.model != 'anonymous' else 'openai',
            "messages": messages,
            "jsonMode": False,
            "stream": stream
        }
        
        headers = {}
        if self.api_key and self.model != 'anonymous':
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        info = await self.get_model_info()
        model_cost = info.get(self.model, {}).get('cost', 0.1)

        if not stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    resp = await client.post(self.url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data['choices'][0]['message']['content']
                    return content, model_cost
                except Exception as e:
                    return f"ERROR: {str(e)}", 0
        else:
            # For streaming, we return an async generator
            async def stream_generator():
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream("POST", self.url, json=payload, headers=headers) as response:
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                                except Exception:
                                    continue
            return stream_generator(), model_cost
