# apps/ai_model/providers/anthropic_provider.py
import json
from typing import AsyncGenerator, Dict, List
from .base import BaseAIProvider

class AnthropicProvider(BaseAIProvider):
    """Anthropic (Claude) provider"""
    
    API_URL = "https://api.anthropic.com/v1"
    
    MODELS = {
        "claude-3-opus": {"max_tokens": 200000, "supports_vision": True},
        "claude-3-sonnet": {"max_tokens": 200000, "supports_vision": True},
        "claude-3-haiku": {"max_tokens": 200000, "supports_vision": True},
        "claude-2.1": {"max_tokens": 200000, "supports_vision": False},
    }
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        # Extract system message if present
        system_message = None
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                filtered_messages.append(msg)
        
        data = {
            "model": model,
            "messages": filtered_messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 2000),
            "temperature": kwargs.get("temperature", 0.7),
        }
        
        if system_message:
            data["system"] = system_message
        
        async with self.session.post(
            f"{self.API_URL}/messages",
            headers=headers,
            json=data
        ) as response:
            response.raise_for_status()
            
            async for line in response.content:
                if line.startswith(b"data: "):
                    try:
                        chunk = json.loads(line[6:])
                        if chunk["type"] == "content_block_delta":
                            yield chunk["delta"]["text"]
                    except json.JSONDecodeError:
                        continue
    
    def validate_model(self, model_name: str) -> bool:
        return model_name in self.MODELS
    
    def get_model_info(self, model_name: str) -> Dict:
        return self.MODELS.get(model_name, {})