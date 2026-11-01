"""Multi-turn terminal chat with temporary conversation history."""

import argparse

from am_core import (
    AMError,
    DEFAULT_MODEL,
    PERSONA,
    api,
    chat_answer,
    metrics,
)

HELP = """Commands:
  /help    Show this help
  /status  Show session settings and loaded models
  /clear   Clear this client's conversation history
  /bye     Exit without stopping Ollama

Blank input is ignored.
Ctrl+C or Ctrl+D at the input prompt exits.
Ctrl+C during a request stops waiting locally.
The server may still be finishing an interrupted request.
"""


def run_chat(
    model=DEFAULT_MODEL,
    context=8192,
    output=1500,
    max_turns=6,
    char_budget=12000,
):
    # Each successful exchange adds one user and one assistant message.
    # Neither history nor responses are saved to disk.
    messages = []
    last_result = None

    print(f"AM local chat | {model} | /help /status /clear /bye")

    while True:
        # Read input and handle terminal exit signals.
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            return

        if not question:
            continue

        # Commands are handled locally and never sent to the model.
        command = question.lower()

        if command == "/bye":
            print("Session ended. Model follows its keep-alive setting.")
            return

        if command == "/help":
            print(HELP)
            continue

        if command == "/clear":
            messages.clear()
            last_result = None
            print("Conversation history cleared in this client.")
            continue

        if command == "/status":
            print(f"Model: {model} | Context: {context} | Output limit: {output}")
            print(f"Saved exchanges: {len(messages) // 2}/{max_turns}")
            print(f"Text budget: {char_budget} characters (not an exact token limit)")

            if last_result:
                print("Last response:", metrics(last_result))

            try:
                loaded = api("/api/ps", timeout=10).get("models", [])
                names = ", ".join(item["name"] for item in loaded)
                print("Loaded models:", names or "none")
            except AMError as error:
                print(error)

            continue

        if question.startswith("/"):
            print("Unknown command. Type /help.")
            continue

        # Bound client history without silently forgetting older exchanges.
        if len(messages) // 2 >= max_turns:
            print("Session turn limit reached. Use /clear to continue.")
            continue

        text_size = sum(len(message["content"]) for message in messages) + len(question)

        if text_size > char_budget:
            print("Text budget exceeded. Shorten input or use /clear.")
            continue

        # Previous measurements provide an additional warning boundary.
        # This is NOT exact token counting for the next request.
        if last_result:
            prior_size = last_result.get("prompt_eval_count", 0) + last_result.get(
                "eval_count", 0
            )

            if prior_size >= context - output:
                print("Previous exchange approached context capacity. Use /clear.")
                continue

        # Prepare a candidate history without changing saved history.
        pending = messages + [
            {"role": "user", "content": question},
        ]

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": PERSONA}] + pending,
            "think": "low",
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "num_ctx": context,
                "num_predict": output,
            },
        }

        print("Waiting for AM...", flush=True)

        # Expected failures return to the input prompt.
        try:
            result = api("/api/chat", payload)
            answer = chat_answer(result)

        except AMError as error:
            print(error)
            print("Exchange not added to history.")
            continue

        except KeyboardInterrupt:
            print("\nRequest interrupted; exchange not saved.")
            print("The server may still be finishing the request.")
            continue

        # Commit both sides together only after a usable response.
        messages = pending + [
            {"role": "assistant", "content": answer},
        ]
        last_result = result

        print("\nAM:", answer)
        print("[" + metrics(result) + "]")

        if result.get("done_reason") == "length":
            print("[Output limit reached; answer may be incomplete.]")


def main(argv=None):
    # Command-line arguments make limits visible and easy to test.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--output", type=int, default=1500)
    parser.add_argument("--max-turns", type=int, default=6)
    parser.add_argument("--char-budget", type=int, default=12000)

    args = parser.parse_args(argv)

    if (
        args.output <= 0
        or args.context <= args.output
        or args.max_turns <= 0
        or args.char_budget <= 0
    ):
        parser.error("Use positive limits, with context greater than output.")

    run_chat(
        args.model,
        args.context,
        args.output,
        args.max_turns,
        args.char_budget,
    )


if __name__ == "__main__":
    main()
