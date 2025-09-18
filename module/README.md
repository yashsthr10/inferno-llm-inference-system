# Module: Inferno

This module provides a LangChain-style Python wrapper for the Inferno API, enabling programmatic access to language model completions via HTTP.

## Architecture Overview
- **File:** `Inferno.py`
- **Class:** `ChatInferno`
- **API:** HTTP (default: `http://localhost:8020/v1/completions`)

## Key Features
- Simple interface for sending prompts and receiving completions
- Configurable model, max tokens, temperature, and API endpoint
- Supports request tracing via optional request ID
- Handles authentication with Bearer tokens
- Robust error handling for network and API errors

## Usage Example
```python
from Inferno import ChatInferno

client = ChatInferno(api_key="YOUR_API_KEY", model="your-model")
result = client.invoke("Hello, world!")
print(result)
```

## Error Handling
- Raises `ConnectionError` for network/API issues
- Raises `ValueError` for invalid or malformed responses

## Customization
- Change `base_url`, `model`, `max_tokens`, and `temperature` via constructor
- Pass a `request_id` for tracing requests

---
For more details, see the code and comments in `Inferno.py`. 