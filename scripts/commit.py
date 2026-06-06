#!/usr/bin/env python3
"""Auto-generate a git commit message from staged changes using Claude."""

import itertools
import os
import readline
import signal
import subprocess
import sys
import threading
import time
import anthropic


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
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        print("Get a key at https://console.anthropic.com/ and add it to your shell:", file=sys.stderr)
        print("  export ANTHROPIC_API_KEY=<your-key>", file=sys.stderr)
        print("See README.md for setup details.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5"

    diff = run(["git", "diff", "--staged"])
    if not diff:
        print("No staged changes. Run `git add` first.")
        sys.exit(1)

    status = run(["git", "status", "--short"])

    stop = threading.Event()
    t = threading.Thread(target=_spin, args=(stop,), daemon=True)
    t.start()
    try:
        response = client.messages.create(
            model=model,
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
    except anthropic.NotFoundError:
        stop.set()
        t.join()
        print(f"Error: model '{model}' not found.", file=sys.stderr)
        print("Check the `kestrelcp.commitModel` setting. See https://docs.claude.com/en/docs/about-claude/models for valid IDs.", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIError as e:
        stop.set()
        t.join()
        print(f"Anthropic API error: {e}", file=sys.stderr)
        sys.exit(1)
    stop.set()
    t.join()

    message = response.content[0].text.strip().strip('"')
    print(f"\n  Suggested commit message (from {model}):")
    print(f"  {message}\n")

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
