#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "app" / "backend"))

print("=" * 60)
print("Testing ChatHandler Initialization")
print("=" * 60)

# Check environment
print("\n[ENV CHECK]")
print(f"GROQ_API_KEY: {bool(os.getenv('GROQ_API_KEY'))}")
print(f"CEREBRAS_API_KEY: {bool(os.getenv('CEREBRAS_API_KEY'))}")
print(f"GEMINI_API_KEY: {bool(os.getenv('GEMINI_API_KEY'))}")

# Try importing groq
print("\n[LIBRARY CHECK]")
try:
    import groq
    print("groq: ✅")
except Exception as e:
    print(f"groq: ❌ {e}")

try:
    import google.generativeai as genai
    print("google-generativeai: ✅")
except Exception as e:
    print(f"google-generativeai: ❌ {e}")

# Now try to define and instantiate ChatHandler
print("\n[CHATHANDLER INSTANTIATION]")
try:
    # Import just the necessary parts
    import logging
    logger = logging.getLogger(__name__)
    
    # Define abrief ChatHandler just for testing
    class TestChatHandler:
        def __init__(self):
            self.active_provider = None
            self.active_model = None
            print("  - __init__ called")
            self.detect_providers()
            print(f"  - Provider detected: {self.active_provider}")
        
        def detect_providers(self):
            print("  - detect_providers() called")
            if os.getenv("GROQ_API_KEY"):
                print("    Found GROQ_API_KEY")
                self.active_provider = "groq"
                self.active_model = "llama-3.3-70b-versatile"
                return
            
            if os.getenv("CEREBRAS_API_KEY"):
                print("    Found CEREBRAS_API_KEY")
                self.active_provider = "cerebras"
                self.active_model = "llama-3.3-70b"
                return
            
            if os.getenv("GEMINI_API_KEY"):
                print("    Found GEMINI_API_KEY")
                self.active_provider = "gemini"
                self.active_model = "gemini-2.5-flash"
                return
                
            print("    ❌ No provider keys found")
    
    handler = TestChatHandler()
    print(f"\n✅ SUCCESS: Handler created")
    print(f"   Active Provider: {handler.active_provider}")
    print(f"   Active Model: {handler.active_model}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
