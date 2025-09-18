from Inferno import ChatInferno

# Initialize client
chat = ChatInferno(
    api_key="c3688792-679a-4340-b0e1-616dda3259b4",
    model="my-quantized-model",
    max_tokens=150,
    temperature=0.8
)

# Execute prompt
try:
    response = chat.invoke("What's the meaning of life?")
    print("Generated:", response)
except Exception as e:
    print("Error:", str(e))