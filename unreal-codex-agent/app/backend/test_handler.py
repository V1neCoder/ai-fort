import sys
import os
from pathlib import Path

# Load env first
from dotenv import load_dotenv
load_dotenv(Path("c:/AI Fort/unreal-codex-agent/.env"))

print("API Keys loaded:")
print(f"  GROQ: {bool(os.getenv('GROQ_API_KEY'))}")
print(f"  CEREBRAS: {bool(os.getenv('CEREBRAS_API_KEY'))}")
print(f"  GEMINI: {bool(os.getenv('GEMINI_API_KEY'))}")

# Import the server module to trigger initialization
sys.path.insert(0, "c:/AI Fort/unreal-codex-agent/app/backend")
try:
    from server import chat_handler
    print("\nChatHandler Status:")
    print(f"  Provider: {chat_handler.active_provider}")
    print(f"  Model: {chat_handler.active_model}")
except Exception as e:
    print(f"Error loading: {e}")
    import traceback
    traceback.print_exc()
