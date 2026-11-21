"""Part 3: the same chatbot with a system prompt that cites sources, logging every Q&A to chat_log.txt."""

from chatbot import CITATION_PROMPT, LOG_FILE, run_cli

if __name__ == "__main__":
    run_cli(CITATION_PROMPT, log_path=LOG_FILE, title="Programming tutor with sources (Part 3)")
