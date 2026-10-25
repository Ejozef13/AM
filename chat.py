import json
import urllib.error
import urllib.request

messages = []

print("AM local chat. Type /bye to exit.")

while True:
    try:
        print()
        question = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("Session ended.")
        break

    if question.lower() == "/bye":
        print("Session ended.")
        break

    if not question:
        continue

    # Prepare the question without changing saved history.
    pending_messages = messages + [
        {"role": "user", "content": question},
    ]

    payload = {
        "model": "gpt-oss:20b",
        "messages": pending_messages,
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

    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.load(response)

        if "error" in result:
            print("Ollama reported an error:", result["error"])
            continue

        answer = result["message"]["content"]

        if not isinstance(answer, str) or not answer.strip():
            print("Ollama returned no usable answer.")
            continue

    except urllib.error.HTTPError as error:
        print(f"Ollama returned HTTP {error.code}.")
        print("Check the installed model and Ollama service logs.")
        continue

    except urllib.error.URLError:
        print("Could not reach Ollama. Check that its service is running.")
        continue

    except (TimeoutError, ConnectionError):
        print("The request timed out or the connection was interrupted.")
        continue

    except (ValueError, KeyError, TypeError):
        print("Ollama returned an unexpected response.")
        continue

    except KeyboardInterrupt:
        print()
        print("Request interrupted; this exchange was not saved.")
        print("The server may still be finishing the request.")
        continue

    # Save the question and answer only after success.
    messages = pending_messages + [
        {"role": "assistant", "content": answer},
    ]

    print()
    print("AM:", answer)

    if result.get("done_reason") == "length":
        print("[Output limit reached; the answer may be incomplete.]")
