"""Part 2: command-line chatbot with multi-turn history and the assignment's system prompt."""

from chatbot import BASE_PROMPT, run_cli

if __name__ == "__main__":
    run_cli(BASE_PROMPT, log_path=None, title="Programming tutor (Part 2)")
