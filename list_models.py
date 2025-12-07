import os
import sys
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.configs.settings import settings
from google import genai

def list_models():
    if not settings.GEMINI_API_KEY:
        print("No API Key found")
        return

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        print("Listing models...")
        for m in client.models.list(config={"page_size": 100}):
            print(f"Model Name: {m.name}")
            # print(f"Object: {m}") 
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
