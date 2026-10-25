"""Entry point: python am.py {on,status,off,chat}."""

import argparse
import subprocess
import time

from am_core import AMError, DEFAULT_MODEL, api
from chat import main as chat_main


def status():
    """Check the real API and show installed and loaded models."""

    installed = api("/api/tags", timeout=10).get("models", [])
    loaded = api("/api/ps", timeout=10).get("models", [])

    print("Local Ollama API: responding")

    names = ", ".join(model["name"] for model in installed)
    print("Installed:", names or "none")

    if not loaded:
        print("Loaded: none")

    for model in loaded:
        vram = model.get("size_vram", 0) / 1e9
        context = model.get("context_length", "unknown")

        print(
            f"Loaded: {model['name']} | "
            f"VRAM reported: {vram:.2f} GB | Context: {context}"
        )


def start():
    """Start the existing service without enabling startup at boot."""

    try:
        api("/api/tags", timeout=2)
        print("Ollama is already responding.")
        return
    except AMError:
        pass

    # Arguments are passed as a list, without invoking a shell.
    subprocess.run(
        ["sudo", "systemctl", "start", "ollama"],
        check=True,
    )

    # Service startup alone is insufficient: wait for an API response.
    for _ in range(20):
        try:
            api("/api/tags", timeout=2)
            print("Ollama API is ready. No model explicitly loaded.")
            return
        except AMError:
            time.sleep(0.5)

    raise AMError("Service start requested, but API readiness was not confirmed.")


def is_loaded(models, name):
    """Match the selected model against Ollama's loaded-model list."""

    return any(item.get("name") == name or item.get("model") == name for item in models)


def unload(model):
    """Unload one selected model; never stop the shared service."""

    loaded = api("/api/ps", timeout=10).get("models", [])

    if not is_loaded(loaded, model):
        print(f"{model} is not listed as loaded; nothing changed.")
        return

    api(
        "/api/generate",
        {
            "model": model,
            "keep_alive": 0,
            "stream": False,
        },
    )

    # Verify the requested state instead of assuming the call worked.
    for _ in range(10):
        loaded = api("/api/ps", timeout=10).get("models", [])

        if not is_loaded(loaded, model):
            print(f"Unloaded {model}. Ollama service remains running.")
            return

        time.sleep(0.5)

    raise AMError("Unload requested, but model is still listed. Check other clients.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("on", help="Start Ollama and check readiness")
    commands.add_parser("status", help="Show installed and loaded models")
    commands.add_parser("chat", help="Open default terminal chat")

    off = commands.add_parser(
        "off",
        help="Unload selected model; leave Ollama running",
    )
    off.add_argument("--model", default=DEFAULT_MODEL)

    args = parser.parse_args(argv)

    try:
        if args.command == "on":
            start()
        elif args.command == "status":
            status()
        elif args.command == "off":
            unload(args.model)
        else:
            chat_main([])

    except (AMError, OSError, subprocess.CalledProcessError) as error:
        print(f"AM: {error}")
        return 1

    except KeyboardInterrupt:
        print("\nOperation interrupted; inspect status before retrying.")
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
