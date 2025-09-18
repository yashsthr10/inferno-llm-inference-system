import requests
from typing import Any, Dict, Optional

class ChatInferno:
    """LangChain-style wrapper for Inferno API"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "default-model",
        max_tokens: int = 100,
        temperature: float = 0.7,
        base_url: str = "localhost/api/consumer",
        request_id: Optional[str] = None
    ):
        """
        Initialize ChatInferno client
        
        Args:
            api_key: Authentication bearer token
            model: Model name to use
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature
            base_url: API base URL
            request_id: Optional request ID for tracing
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base_url = base_url
        self.endpoint = f"http://{base_url}/v1/completions"
        self.request_id = request_id

    def invoke(self, prompt: str) -> str:
        """
        Execute completion request and return generated text
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated text response
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
            "request_id": self.request_id
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=60  # 60-second timeout
            )
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["text"]
            else:
                raise ValueError("Invalid response format: Missing choices")
                
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            error_msg = f"API error ({status}): "
            try:
                error_details = e.response.json().get("error", str(e))
                error_msg += error_details
            except:
                error_msg += str(e)
            raise ConnectionError(error_msg)
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Network error: {str(e)}")
            
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Response parsing error: {str(e)}")