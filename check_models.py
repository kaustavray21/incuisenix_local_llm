import requests
import sys

def check_ollama_status():
    base_url = "http://localhost:11434"
    required_models = {
        "deepseek-r1:14b": False,
        "nomic-embed-text": False
    }

    print(f"1. Connecting to Ollama at {base_url}...")

    try:
        # Check if Ollama is running
        response = requests.get(f"{base_url}/api/tags")
        
        if response.status_code == 200:
            print("   ✅ Success: Ollama is running.\n")
            
            # Parse available models
            models_data = response.json().get('models', [])
            available_model_names = [m['name'] for m in models_data]
            
            print("2. Checking for required models...")
            
            # Check for partial matches (e.g., 'nomic-embed-text:latest' matches 'nomic-embed-text')
            for required in required_models.keys():
                for available in available_model_names:
                    if required in available:
                        required_models[required] = True
                        break
            
            # Report status
            all_present = True
            for model, present in required_models.items():
                if present:
                    print(f"   ✅ Found: {model}")
                else:
                    print(f"   ❌ MISSING: {model}")
                    all_present = False
            
            print("-" * 30)
            if all_present:
                print("🚀 System Ready! All required models are available.")
            else:
                print("⚠️  Some models are missing. Run the following commands in your terminal:")
                if not required_models["deepseek-r1:14b"]:
                    print("   ollama pull deepseek-r1:14b")
                if not required_models["nomic-embed-text"]:
                    print("   ollama pull nomic-embed-text")
                    
        else:
            print(f"   ❌ Error: Ollama responded with status code {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("\n   ❌ CONNECTION FAILED: Could not connect to Ollama.")
        print("   ---------------------------------------------------")
        print("   Please ensure Ollama is running. You can start it by:")
        print("   1. Opening the Ollama app (Windows/Mac)")
        print("   2. Or running 'ollama serve' in your terminal (Linux)")

if __name__ == "__main__":
    check_ollama_status()