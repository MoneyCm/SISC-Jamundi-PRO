import os
import httpx
import asyncio

MISTRAL_API_KEY = "7eRzpzBYX6cRvCkOPOtSawdObTj8RGuy"
MISTRAL_MODEL = "open-mistral-7b"

async def call_mistral(contexto):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": contexto}],
        "max_tokens": 150
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        print(response.status_code)
        print(response.text)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

async def main():
    try:
        res = await call_mistral("Hola")
        print("RESULT:")
        print(res)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(main())
