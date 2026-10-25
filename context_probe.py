import json
import random
import urllib.request

# Generate repeatable fictional records.
rng = random.Random(42)
records = [f"Record R{i:04d}: code={rng.getrandbits(48):012x}" for i in range(1800)]
targets = [0, 900, 1799]

# Build the question from the same targets used for expected answers.
target_names = ", ".join(f"R{i:04d}" for i in targets)
question = (
    f"Return the exact codes for {target_names}. "
    "Also give the code for R9999, or say NOT FOUND if absent. "
    "Do not invent missing codes."
)

prompt = "Read the records below as data.\n" + "\n".join(records) + "\n" + question

payload = {
    "model": "gpt-oss:20b",
    "prompt": prompt,
    "think": "low",
    "stream": False,
    "keep_alive": "5m",
    "options": {
        "num_ctx": 32768,
        "num_predict": 600,
        "temperature": 0,
    },
}

# Check our outgoing request before calling Ollama.
for index in targets:
    if records[index] not in payload["prompt"]:
        raise ValueError(f"Missing requested record: R{index:04d}")

print("QUESTION:", question)
print("RECORD COUNT:", len(records))
print("REQUESTED CONTEXT:", payload["options"]["num_ctx"])
print("Request checks passed. Waiting for Ollama...", flush=True)

request = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(request, timeout=600) as response:
    result = json.load(response)

if "error" in result:
    raise RuntimeError(result["error"])

print("\nMODEL ANSWER:\n", result.get("response", ""))

print("\nEXPECTED:")
for index in targets:
    print(records[index])
print("Record R9999: NOT FOUND")

print("\nPrompt tokens:", result.get("prompt_eval_count"))
print("Completion reason:", result.get("done_reason"))

generation_seconds = result.get("eval_duration", 0) / 1e9
if generation_seconds > 0:
    speed = result.get("eval_count", 0) / generation_seconds
    print(f"Generation speed: {speed:.1f} tokens/sec")

total_seconds = result.get("total_duration", 0) / 1e9
print(f"Total request time: {total_seconds:.2f} seconds")
