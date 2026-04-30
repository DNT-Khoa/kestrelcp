#!/usr/bin/env python3
"""Auto-generate a git commit message from staged changes using Claude."""

import itertools
import readline
import signal
import subprocess
import sys
import threading
import time
import anthropic

client = anthropic.Anthropic()


def _spin(stop: threading.Event) -> None:
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    for i in itertools.cycle(range(len(frames))):
        if stop.is_set():
            break
        sys.stdout.write(f"\r  Generating commit message {frames[i]} ")
        sys.stdout.flush()
        time.sleep(0.08)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def main() -> None:
    diff = run(["git", "diff", "--staged"])
    if not diff:
        print("No staged changes. Run `git add` first.")
        sys.exit(1)

    status = run(["git", "status", "--short"])

    stop = threading.Event()
    t = threading.Thread(target=_spin, args=(stop,), daemon=True)
    t.start()
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=128,
        system=[{
            "type": "text",
            "text": (
                "You generate concise git commit messages following the Conventional Commits spec with an emoji prefix.\n"
                "Format: <emoji> <type>(<optional scope>): <short description>\n"
                "Emoji map:\n"
                "  feat     → ✨\n"
                "  fix      → 🐛\n"
                "  docs     → 📝\n"
                "  style    → 💄\n"
                "  refactor → ♻️\n"
                "  test     → ✅\n"
                "  chore    → 🔧\n"
                "  perf     → ⚡️\n"
                "  ci       → 👷\n"
                "  revert   → ⏪️\n"
                "Rules: one line only, no period, under 72 characters, lowercase type and description.\n"
                "Output only the commit message — no explanation, no quotes."
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"Git status:\n{status}\n\nDiff:\n{diff[:8000]}",
        }],
    )
    stop.set()
    t.join()

    message = response.content[0].text.strip().strip('"')
    print(f"\n  {message}\n")

    confirm = input("Commit with this message? [Y/n/e] ").strip().lower()
    if confirm == "n":
        print("Aborted.")
        sys.exit(0)
    elif confirm == "e":
        def _abort(*_):
            print("\nAborted.")
            sys.exit(0)

        old_sigtstp = signal.signal(signal.SIGTSTP, _abort)
        readline.set_startup_hook(lambda: readline.insert_text(message))
        # libedit (macOS) uses different binding syntax than GNU readline
        if "libedit" in (readline.__doc__ or ""):
            readline.parse_and_bind('bind "^[" ed-end-of-file')
        else:
            readline.parse_and_bind(r'"\e": abort')
        try:
            message = input("Edit: ").strip() or message
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)
        finally:
            readline.set_startup_hook()
            signal.signal(signal.SIGTSTP, old_sigtstp)

    subprocess.run(["git", "commit", "-m", message], check=True)


if __name__ == "__main__":
    main()
