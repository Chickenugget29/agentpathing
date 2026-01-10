"""Terminal interface for the Atlas-style FOL translator."""

from __future__ import annotations

from translator import translate


INTRO = """\
Chain-of-Thought → FOL translator
Paste multi-step reasoning (numbered sections, colon steps, bullets)
and receive structured first-order logic facts. Blank line or 'exit' quits.
"""


def cli() -> None:
    """Interactive CLI loop."""
    print(INTRO)
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break

        if not text or text.lower() in {"exit", "quit"}:
            break

        fol = translate(text)
        if fol:
            print(f"FOL: {fol}")
        else:
            print("Could not translate that request.")


if __name__ == "__main__":
    cli()
