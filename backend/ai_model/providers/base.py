from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
import aiohttp
import logging

logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """Base class for AI model providers"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion from the model"""
        pass
    
    @abstractmethod
    async def get_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> str:
        """Get non-streaming completion from the model"""
        pass
    
    @abstractmethod
    def validate_model(self, model_name: str) -> bool:
        """Validate if model is available"""
        pass
    
    @abstractmethod
    def get_model_info(self, model_name: str) -> Dict:
        """Get model information"""
        pass
    
    def format_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Format messages for the provider's API"""
        return messages
    
    async def handle_error(self, error: Exception, model: str):
        """Handle provider-specific errors"""
        logger.error(f"Error with {self.__class__.__name__} for model {model}: {error}")
        raise error