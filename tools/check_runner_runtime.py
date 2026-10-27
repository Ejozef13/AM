"""Check the Docker execution boundary using a trusted diagnostic program."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
PIN_FILE = ROOT / "infrastructure" / "python-runner-image.txt"

# This is our own diagnostic code, not a student submission.
PROBE = """
import errno
import json
import os
from pathlib import Path

try:
    Path("/am-write-test").write_text("test")
    root_write_errno = None
except OSError as error:
    root_write_errno = error.errno

temporary = Path("/tmp/am-write-test")
temporary.write_text("test")

status = {}
for line in Path("/proc/self/status").read_text().splitlines():
    if ":" in line:
        key, value = line.split(":", 1)
        status[key] = value.strip()

print(json.dumps({
    "uid": os.getuid(),
    "gid": os.getgid(),
    "root_write_errno": root_write_errno,
    "tmp_writable": temporary.read_text() == "test",
    "interfaces": sorted(os.listdir("/sys/class/net")),
    "effective_capabilities": int(status["CapEff"], 16),
    "no_new_privileges": status["NoNewPrivs"],
}))
"""


def docker(*arguments, **options):
    """Use cached sudo authorization rather than hanging on a hidden prompt."""
    return subprocess.run(
        ["sudo", "-n", "docker", *arguments],
        **options,
    )


def pin_image():
    """Record the downloaded digest directly, avoiding transcription errors."""
    result = docker(
        "image",
        "inspect",
        "python:3.14-slim",
        "--format",
        "{{json .RepoDigests}}",
        check=True,
        capture_output=True,
        text=True,
    )

    digests = json.loads(result.stdout)
    image = next(item for item in digests if item.startswith("python@sha256:"))

    if not re.fullmatch(r"python@sha256:[0-9a-f]{64}", image):
        raise ValueError("Unexpected image digest.")

    PIN_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Refuse to replace an existing pin accidentally.
    with PIN_FILE.open("x", encoding="utf-8") as handle:
        handle.write(image + "\n")

    print("Saved runtime pin:", PIN_FILE)


def check_runtime():
    """Run the trusted probe with the intended container restrictions."""
    image = PIN_FILE.read_text(encoding="utf-8").strip()

    if not re.fullmatch(r"python@sha256:[0-9a-f]{64}", image):
        raise ValueError("Invalid runtime pin.")

    name = "am-runtime-check-" + uuid.uuid4().hex

    arguments = [
        "run",
        "--name",
        name,
        "--rm",
        "--pull",
        "never",
        "--network",
        "none",
        "--read-only",
        "--user",
        "65534:65534",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--memory",
        "128m",
        "--memory-swap",
        "128m",
        "--cpus",
        "0.5",
        "--pids-limit",
        "32",
        "--ulimit",
        "nofile=64:64",
        "--ulimit",
        "cpu=2:2",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m",
        image,
        "python",
        "-I",
        "-B",
        "-c",
        PROBE,
    ]

    try:
        result = docker(
            *arguments,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        observed = json.loads(result.stdout)

    finally:
        # Also clean up if the client times out or is interrupted.
        cleanup = docker(
            "rm",
            "-f",
            name,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Normally --rm has already removed the container.
        if cleanup.returncode and "No such container" not in cleanup.stderr:
            print("Cleanup needs inspection:", cleanup.stderr.strip())

    checks = {
        "Unprivileged user": observed["uid"] == 65534,
        "Unprivileged group": observed["gid"] == 65534,
        "Read-only root filesystem": observed["root_write_errno"] == 30,
        "Temporary workspace writable": observed["tmp_writable"],
        "Only loopback network interface": observed["interfaces"] == ["lo"],
        "No effective Linux capabilities": observed["effective_capabilities"] == 0,
        "Privilege escalation disabled": observed["no_new_privileges"] == "1",
    }

    for description, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {description}")

    if not all(checks.values()):
        raise ValueError("Runtime boundary checks failed.")

    print("\nRuntime probe passed. No student code was executed.")
    print("Resource-limit behavior still needs separate tests.")
    print("This is a local prototype, not a public hostile-code service.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pin",
        action="store_true",
        help="Record the downloaded runtime image before checking it",
    )
    args = parser.parse_args()

    try:
        if args.pin:
            pin_image()
        check_runtime()

    except subprocess.CalledProcessError as error:
        print("Docker operation failed:")
        print(error.stderr or str(error))
        return 1

    except (
        OSError,
        ValueError,
        StopIteration,
        subprocess.TimeoutExpired,
    ) as error:
        print("Runtime check failed:", error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
