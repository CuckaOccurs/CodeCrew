import requests
import sys

SERVER_IP = "10.0.0.68"
PORT = 3030

def ask_server(prompt):
    url = f"http://{SERVER_IP}:{PORT}/chat"
    payload = {"text": prompt}
    
    print(f"Sending to {SERVER_IP}...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        print("\nAI Response:")
        print(result.get("response"))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ask_server(" ".join(sys.argv[1:]))
    else:
        while True:
            p = input("\n> ")
            if p.lower() in ["exit", "quit"]: break
            ask_server(p)
