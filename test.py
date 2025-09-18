import httpx
import json
import asyncio
import sys
import websockets
import time
import statistics

# --- Configuration ---
HTTP_API_TOKEN = "c3688792-679a-4340-b0e1-616dda3259b4" # <-- !!! REPLACE THIS PLACEHOLDER !!!
WEBSOCKET_SECRET_KEY = "yksuthar@h46sg3qe7665"
BASE_URL = "localhost/api/consumer" # Assuming a port, adjust if needed
PAYLOAD = {
    "model": "my-quantized-model",
    "prompt": "hi do you like dragon ball z?",
    "max_tokens": 500,
    "temperature": 0.8
}

# --- Benchmark Configuration ---
BENCHMARK_QUERIES = [
    "Explain the theory of relativity in 100 words.",
    "Write a short story about a robot who discovers music.",
    "What are the top 5 benefits of a regular exercise routine?",
    "Generate a list of 10 creative names for a new coffee shop.",
    "Summarize the plot of the movie 'Inception'.",
    "Translate the phrase 'Hello, how are you?' into French.",
    "Write a python function to calculate the factorial of a number.",
    "What is the capital of Australia and what is it famous for?",
    "Describe the process of photosynthesis in simple terms.",
    "Compose a short poem about the rain."
]

# ==============================================================================
#                            BENCHMARKING FUNCTIONS
# ==============================================================================

async def benchmark_http_stream(client: httpx.AsyncClient, prompt: str):
    """Runs a single streaming request and returns performance metrics."""
    url = f"http://{BASE_URL}/v1/completions"
    headers = {"Authorization": f"Bearer {HTTP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {**PAYLOAD, "prompt": prompt, "stream": True}

    metrics = {
        "success": False, "ttft": None, "total_latency": None,
        "tps": None, "output_tokens": 0
    }
    
    start_time = time.monotonic()
    first_token_time = None
    
    try:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            
            full_response_text = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    if first_token_time is None:
                        first_token_time = time.monotonic() # Capture time of first data chunk

                    if line.strip() == "data: [DONE]":
                        break
                        
                    data = json.loads(line[len("data: "):])
                    text_chunk = data.get("choices", [{}])[0].get("text", "")
                    if text_chunk:
                         full_response_text += text_chunk
            
            # Finalize metrics upon successful completion
            end_time = time.monotonic()
            metrics["success"] = True
            metrics["total_latency"] = end_time - start_time
            metrics["output_tokens"] = len(full_response_text.split())

            if first_token_time:
                metrics["ttft"] = first_token_time - start_time
                # Tokens per second is calculated on the generation time after the first token
                generation_time = end_time - first_token_time
                if generation_time > 0 and metrics["output_tokens"] > 1:
                    metrics["tps"] = (metrics["output_tokens"] - 1) / generation_time
                    
    except httpx.HTTPError as e:
        print(f"\n[BENCHMARK ERROR] Request failed for prompt '{prompt[:30]}...': {e}")
    except Exception as e:
        print(f"\n[BENCHMARK EXCEPTION] An unexpected error occurred: {e}")
        
    return metrics


async def run_benchmark(benchmark_func, queries):
    """Runs the specified benchmark function for all queries and prints a summary."""
    print(f"\n" + "="*20 + f" RUNNING BENCHMARK: {benchmark_func.__name__} " + "="*20)
    print(f"Running {len(queries)} queries...")

    results = []
    async with httpx.AsyncClient(timeout=None) as client:
        for i, query in enumerate(queries):
            print(f"  [{i+1}/{len(queries)}] Running prompt: '{query[:50]}...'")
            result = await benchmark_func(client, query)
            results.append(result)
            await asyncio.sleep(1) # Small delay to avoid overwhelming the server

    print_summary_statistics(results)


def print_summary_statistics(results):
    """Calculates and prints summary statistics from benchmark results."""
    successful_results = [r for r in results if r["success"]]
    
    print("\n" + "="*25 + " BENCHMARK SUMMARY " + "="*25)
    print(f"Total Requests: {len(results)}")
    print(f"Successful:     {len(successful_results)}")
    print(f"Failed:         {len(results) - len(successful_results)}")
    
    if not successful_results:
        print("\nNo successful requests to analyze.")
        return

    # Extracting data for analysis
    ttfts = [r["ttft"] for r in successful_results if r.get("ttft") is not None]
    latencies = [r["total_latency"] for r in successful_results]
    tps_list = [r["tps"] for r in successful_results if r.get("tps") is not None]
    output_tokens = [r["output_tokens"] for r in successful_results]
    
    # --- Helper to format stats ---
    def get_stats(data):
        if not data:
            return "N/A", "N/A", "N/A", "N/A"
        return (
            f"{statistics.mean(data):.3f}",
            f"{min(data):.3f}",
            f"{max(data):.3f}",
            f"{statistics.stdev(data):.3f}" if len(data) > 1 else "N/A"
        )
        
    ttft_avg, ttft_min, ttft_max, ttft_std = get_stats(ttfts)
    lat_avg, lat_min, lat_max, lat_std = get_stats(latencies)
    tps_avg, tps_min, tps_max, tps_std = get_stats(tps_list)
    tok_avg, _, _, _ = get_stats(output_tokens) # Only average is interesting for tokens

    print("\n--- PERFORMANCE METRICS ---")
    print(f"{'Metric':<25} | {'Average':<10} | {'Min':<10} | {'Max':<10} | {'Std Dev':<10}")
    print("-" * 75)
    print(f"{'Time to First Token (s)':<25} | {ttft_avg:<10} | {ttft_min:<10} | {ttft_max:<10} | {ttft_std:<10}")
    print(f"{'Total Latency (s)':<25} | {lat_avg:<10} | {lat_min:<10} | {lat_max:<10} | {lat_std:<10}")
    print(f"{'Output Tokens/Second':<25} | {tps_avg:<10} | {tps_min:<10} | {tps_max:<10} | {tps_std:<10}")
    print(f"{'Avg Output Tokens':<25} | {tok_avg:<10} | {'-':<10} | {'-':<10} | {'-':<10}")
    print("=" * 75)


# ==============================================================================
#                            ORIGINAL TEST FUNCTIONS
# ==============================================================================

async def test_http_stream():
    """Tests the HTTP endpoint with stream=True."""
    print("\n" + "="*20 + " TESTING HTTP STREAM " + "="*20)
    url = f"http://{BASE_URL}/v1/completions"
    headers = {"Authorization": f"Bearer {HTTP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {**PAYLOAD, "stream": True}

    print(f"[INFO] Sending request to {url}")
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                print(f"[INFO] Response status: {response.status_code}")
                response.raise_for_status()

                full_response = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        if line.strip() == "data: [DONE]": break
                        data = json.loads(line[len("data: "):])
                        text_chunk = data.get("choices", [{}])[0].get("text", "")
                        print(text_chunk, end="", flush=True)
                        full_response += text_chunk
                print("\n[STREAM END]")
    except httpx.HTTPStatusError as e:
        print(f"\n[ERROR] Server returned error status: {e.response.status_code}")
        error_body = await e.response.aread()
        print(f"[ERROR BODY] {error_body.decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"\n[EXCEPTION] An unexpected error occurred: {e}")


async def test_http_non_stream():
    """Tests the HTTP endpoint with stream=False."""
    print("\n" + "="*20 + " TESTING HTTP NON-STREAM " + "="*20)
    url = f"http://{BASE_URL}/v1/completions"
    headers = {"Authorization": f"Bearer {HTTP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {**PAYLOAD, "stream": False}

    print(f"[INFO] Sending request to {url}")
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(url, json=payload, headers=headers)
            print(f"[INFO] Response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            print("[INFO] Full response received:")
            print(json.dumps(data, indent=2))
            text = data.get("choices", [{}])[0].get("text")
            print("\n[Extracted Text]:", text)

    except httpx.HTTPStatusError as e:
        print(f"\n[ERROR] Server returned error status: {e.response.status_code}")
        print(f"[ERROR BODY] {e.response.text}") # .text is fine for non-streaming
    except Exception as e:
        print(f"\n[EXCEPTION] An unexpected error occurred: {e}")


async def test_websocket():
    """Tests the WebSocket endpoint."""
    print("\n" + "="*20 + " TESTING WEBSOCKET " + "="*20)
    uri = f"ws://{BASE_URL}/v1/completions?token={WEBSOCKET_SECRET_KEY}"
    payload = {**PAYLOAD, "stream": True} # WebSockets are inherently streaming
    
    print(f"[INFO] Connecting to {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print("[INFO] WebSocket connection established.")
            await websocket.send(json.dumps(payload))
            print("[INFO] Sent payload. Waiting for response...")

            while True:
                message = await websocket.recv()
                if message == "[DONE]": break
                data = json.loads(message)
                text_chunk = data.get("choices", [{}])[0].get("text", "")
                print(text_chunk, end="", flush=True)
            print("\n[STREAM END]")
    except Exception as e:
        print(f"\n[EXCEPTION] An unexpected error occurred: {e}")


async def main():
    """Main function to run the selected test or benchmark."""
    valid_modes = ["http", "http-no-stream", "ws", "benchmark-stream"]
    
    if len(sys.argv) < 2 or sys.argv[1] not in valid_modes:
        print(f"Usage: python test_script.py [{'|'.join(valid_modes)}]")
        return

    test_mode = sys.argv[1]
    
    # --- Route to the correct function ---
    if test_mode == "http":
        await test_http_stream()
    elif test_mode == "http-no-stream":
        await test_http_non_stream()
    elif test_mode == "ws":
        await test_websocket()
    elif test_mode == "benchmark-stream":
        await run_benchmark(benchmark_http_stream, BENCHMARK_QUERIES)

if __name__ == "__main__":
    asyncio.run(main())