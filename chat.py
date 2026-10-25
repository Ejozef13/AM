import json
import urllib.request

question = input("You: ").strip()
if not question:
    raise SystemExit("No question entered.")

payload = {
    "model": "gpt-oss:20b",
    "messages": [
        {"role": "user", "content": question},
    ],
    "think": "low",
    "stream": False,
    "keep_alive": "5m",
    "options": {
        "num_ctx": 8192,
        "num_predict": 1500,
    },
}

request = urllib.request.Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

print("Waiting for AM...", flush=True)

with urllib.request.urlopen(request, timeout=600) as response:
    result = json.load(response)

if "error" in result:
    raise RuntimeError(result["error"])

print("\nAM:", result["message"]["content"])

if result.get("done_reason") == "length":
    print("\n[Output limit reached; the answer may be incomplete.]")
