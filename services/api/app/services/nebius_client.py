import httpx
import json
import time
import os
from typing import Optional, List, Dict, Any
from app.core.config import settings


class ProviderConfigurationError(RuntimeError):
    """Raised when no AI provider credentials are configured."""


class ProviderResponseError(RuntimeError):
    """Raised when the provider response does not match the chat API shape."""


class NebiusClient:
    def __init__(self):
        nebius_key = settings.nebius_api_key or os.getenv("NEBIUS_API_KEY")
        nvidia_nim_key = settings.nvidia_nim_api_key or os.getenv("NVIDIA_NIM_API_KEY")
        if nebius_key:
            self.api_key = nebius_key
            self.base_url = settings.nebius_base_url
            self.model = settings.nebius_model
            self.provider = "nebius"
        elif nvidia_nim_key:
            self.api_key = nvidia_nim_key
            self.base_url = settings.nvidia_nim_base_url
            self.model = settings.nvidia_nim_model
            self.provider = "nvidia_nim"
        else:
            self.api_key = None
            self.base_url = settings.nebius_base_url
            self.model = settings.nebius_model
            self.provider = None
        self.base_url = self.base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
        )
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError(
                "Configure NEBIUS_API_KEY or NVIDIA_NIM_API_KEY"
            )
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        start_time = time.time()
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise TypeError("response body is not an object")
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not text")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                "The AI provider returned an invalid chat completion response"
            ) from exc
        usage = data.get("usage")
        
        return {
            "content": content,
            "tokens_used": usage.get("total_tokens") if isinstance(usage, dict) else None,
            "duration_ms": duration_ms,
        }
    
    async def close(self):
        await self.client.aclose()

nebius_client = NebiusClient()