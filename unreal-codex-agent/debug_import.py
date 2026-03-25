import sys
import traceback
sys.path.insert(0, 'c:/AI Fort/unreal-codex-agent/app/backend')

try:
    import server
    print("✅ Server imported successfully")
    print("chat_handler exists:", hasattr(server, 'chat_handler'))
    print("chat_handler value:", server.chat_handler if hasattr(server, 'chat_handler') else "N/A")
    
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
