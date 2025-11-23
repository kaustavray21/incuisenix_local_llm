import requests
import sys

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def check_ollama_status():
    base_url = "http://localhost:11434"
    
    # Updated to the faster 7b model based on our debugging session
    required_models = {
        "deepseek-r1:7b": False, 
        "nomic-embed-text": False
    }

    print(f"1. Connecting to Ollama at {base_url}...")

    try:
        # Check if Ollama is running (using tags endpoint)
        response = requests.get(f"{base_url}/api/tags")
        
        if response.status_code == 200:
            print("   ✅ Success: Ollama is running.\n")
            
            # --- NEW: Check which models are currently running in memory ---
            print("2. Checking currently running models (in memory)...")
            try:
                ps_response = requests.get(f"{base_url}/api/ps")
                if ps_response.status_code == 200:
                    running_models = ps_response.json().get('models', [])
                    if running_models:
                        for model in running_models:
                            name = model.get('name', 'Unknown')
                            size = model.get('size', 0)
                            vram = model.get('size_vram', 0)
                            print(f"   🏃 ACTIVE: {name}")
                            print(f"      └─ Total Size: {format_bytes(size)} | VRAM Usage: {format_bytes(vram)}")
                    else:
                        print("   💤 No models are currently loaded in memory (Idle).")
                else:
                    print(f"   ⚠️ Could not fetch running models. (API Status: {ps_response.status_code})")
            except Exception as e:
                print(f"   ⚠️ Error checking running models: {e}")
            print("-" * 30)

            # --- Check for available models (On Disk) ---
            print("3. Checking for required models on disk...")
            
            # Parse available models
            models_data = response.json().get('models', [])
            available_model_names = [m['name'] for m in models_data]
            
            # Check for partial matches
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
                if not required_models["deepseek-r1:7b"]:
                    print("   ollama pull deepseek-r1:7b")
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