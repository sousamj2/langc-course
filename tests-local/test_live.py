import asyncio
import sys
from pathlib import Path

# Add project root to python path to allow imports from app if needed
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from google import genai
from google.genai import types

# ==========================================
# CONFIGURATION
# Add your Gemini API key directly here (do not use .env)
GEMINI_API_KEY = "my-key-here"

# Model to test (e.g., "gemini-3.1-flash-live-preview", "gemini-3.5-live-translate-preview")
MODEL_NAME = "gemini-3.1-flash-live-preview"
# ==========================================

async def main():
    if GEMINI_API_KEY == "api-key-here":
        print("ERROR: Please replace the placeholder 'api-key-here' with your actual Gemini API key in this file.")
        sys.exit(1)

    print(f"Initializing Gemini Client with provided API Key...")
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(api_version="v1alpha")
    )
    
    prompt = "What is 2 + 2 ?"
    print(f"Connecting to Gemini Live Session using model: '{MODEL_NAME}'")
    print(f"Sending prompt: '{prompt}'")
    
    # Configure the live session for audio responses with output transcription enabled
    config_live = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription=types.AudioTranscriptionConfig()
    )
    
    try:
        # Connect to the real-time session
        async with client.aio.live.connect(model=MODEL_NAME, config=config_live) as session:
            # Send the text content turn
            await session.send_client_content(
                turns=types.Content(
                    role='user',
                    parts=[types.Part.from_text(text=prompt)]
                ),
                turn_complete=True
            )
            
            print("Receiving stream: ", end="", flush=True)
            
            # Read incoming text transcript chunks
            async for response in session.receive():
                if response.server_content and response.server_content.output_transcription:
                    part = response.server_content.output_transcription
                    if part.text:
                        print(part.text, end="", flush=True)
                
                # Check for turn completion signal
                if response.server_content and response.server_content.turn_complete:
                    break
            
            print("\nStream finished successfully.")
            
    except Exception as e:
        print(f"\nFailed to run Gemini Live session: {e}")
        try:
            print("\nAttempting to list available models to find a compatible one...")
            models = list(client.models.list())
            live_models = []
            for m in models:
                methods = getattr(m, 'supported_generation_methods', None) or getattr(m, 'supported_methods', None) or []
                if 'bidiGenerateContent' in methods or 'live' in m.name.lower():
                    live_models.append(m.name)
            
            if live_models:
                print("Here are the Live-compatible models available for your API key:")
                for name in live_models:
                    print(f"  - {name}")
            else:
                print("No models with Live support explicitly advertised. All available models:")
                for m in models:
                    print(f"  - {m.name}")
                if models:
                    try:
                        print(f"\nDebug - Model fields: {list(models[0].__dict__.keys())}")
                    except Exception:
                        pass
        except Exception as list_err:
            print(f"Could not list models: {list_err}")

if __name__ == "__main__":
    asyncio.run(main())
