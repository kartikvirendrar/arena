# apps/ai_model/providers/openai_provider.py
import json
from typing import AsyncGenerator, Dict, List
from .base import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider"""
    
    API_URL = "https://api.openai.com/v1"
    
    MODELS = {
        "gpt-4-turbo": {"max_tokens": 128000, "supports_vision": True},
        "gpt-4": {"max_tokens": 8192, "supports_vision": False},
        "gpt-3.5-turbo": {"max_tokens": 16385, "supports_vision": False},
        "gpt-4o": {"max_tokens": 128000, "supports_vision": True},
        "gpt-4o-mini": {"max_tokens": 128000, "supports_vision": True},
    }
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        
        async with self.session.post(
            f"{self.API_URL}/chat/completions",
            headers=headers,
            json=data
        ) as response:
            response.raise_for_status()
            
            async for line in response.content:
                if line.startswith(b"data: "):
                    if line.strip() == b"data: [DONE]":
                        break
                    
                    try:
                        chunk = json.loads(line[6:])
                        if chunk["choices"][0]["delta"].get("content"):
                            yield chunk["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        continue
    
    async def get_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        
        async with self.session.post(
            f"{self.API_URL}/chat/completions",
            headers=headers,
            json=data
        ) as response:
            response.raise_for_status()
            result = await response.json()
            return result["choices"][0]["message"]["content"]
    
    def validate_model(self, model_name: str) -> bool:
        return model_name in self.MODELS
    
    def get_model_info(self, model_name: str) -> Dict:
        return self.MODELS.get(model_name, {})