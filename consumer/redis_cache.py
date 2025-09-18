import redis
import json
import hashlib
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_client = None
        self.cache_ttl = 3600  # 1 hour default TTL
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Successfully connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, prompt: str, model: str, max_tokens: int, temperature: float) -> str:
        """Generate a unique cache key based on prompt and parameters"""
        # Create a hash of the prompt and parameters
        cache_string = f"{prompt}:{model}:{max_tokens}:{temperature}"
        return f"vllm_cache:{hashlib.md5(cache_string.encode()).hexdigest()}"
    
    def get_cached_response(self, prompt: str, model: str, max_tokens: int, temperature: float) -> Optional[Dict[str, Any]]:
        """Get cached response if available"""
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, skipping cache lookup")
            return None
        
        try:
            cache_key = self._generate_cache_key(prompt, model, max_tokens, temperature)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                response_data = json.loads(cached_data)
                logger.info(f"✅ Cache hit for prompt: {prompt[:50]}...")
                return response_data
            else:
                logger.info(f"❌ Cache miss for prompt: {prompt[:50]}...")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error reading from cache: {e}")
            return None
    
    def cache_response(self, prompt: str, model: str, max_tokens: int, temperature: float, 
                      response: str, request_id: str) -> bool:
        """Cache the response"""
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, skipping cache write")
            return False
        
        try:
            cache_key = self._generate_cache_key(prompt, model, max_tokens, temperature)
            cache_data = {
                "prompt": prompt,
                "response": response,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "cached_at": "cache_hit",
                "original_request_id": request_id
            }
            
            # Cache for 1 hour
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(cache_data)
            )
            
            logger.info(f"✅ Cached response for prompt: {prompt[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error writing to cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.redis_client:
            return {"error": "Redis not connected"}
        
        try:
            # Get all cache keys
            cache_keys = self.redis_client.keys("vllm_cache:*")
            total_cached = len(cache_keys)
            
            # Get memory usage
            info = self.redis_client.info()
            memory_usage = info.get('used_memory_human', 'N/A')
            
            return {
                "total_cached_items": total_cached,
                "memory_usage": memory_usage,
                "cache_ttl_seconds": self.cache_ttl
            }
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {"error": str(e)}
    
    def clear_cache(self) -> bool:
        """Clear all cached responses"""
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, cannot clear cache")
            return False
        
        try:
            cache_keys = self.redis_client.keys("vllm_cache:*")
            if cache_keys:
                self.redis_client.delete(*cache_keys)
                logger.info(f"✅ Cleared {len(cache_keys)} cached items")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing cache: {e}")
            return False 