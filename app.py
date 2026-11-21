"""Part 4: Streamlit web interface for the chatbot.

    streamlit run app.py

The conversation lives in st.session_state, so it survives Streamlit's rerun on
every message and the chat continues in the browser.
"""

from __future__ import annotations

import re

import streamlit as st

from chatbot import BASE_PROMPT, CITATION_PROMPT, LOG_FILE, ChatSession
from llm_client import get_model, make_client

PROMPTS = {
    "Programming tutor with sources (Part 3)": CITATION_PROMPT,
    "Basic programming tutor (Part 2)": BASE_PROMPT,
}


def render(text: str) -> None:
    """Markdown joins single newlines, so keep each "[n] source" line on its own line."""
    st.markdown(re.sub(r"\n(?=\[\d+\])", "  \n", text))


st.set_page_config(page_title="Programming Tutor Chatbot", page_icon="💬")
st.title("💬 Programming Tutor")
st.caption(f"A friendly assistant who helps you learn programming · model: `{get_model()}`")

with st.sidebar:
    st.header("Settings")
    prompt_name = st.radio("System prompt", list(PROMPTS), index=0)
    log_enabled = st.toggle("Log Q&A to chat_log.txt", value=True)
    if st.button("New chat", use_container_width=True):
        st.session_state.pop("session", None)
    with st.expander("Current system prompt"):
        st.code(PROMPTS[prompt_name], language="markdown", wrap_lines=True)

# Start a new session when there is none yet or the prompt setting changed.
session: ChatSession | None = st.session_state.get("session")
if session is None or session.system_prompt != PROMPTS[prompt_name]:
    session = ChatSession(make_client(), get_model(), PROMPTS[prompt_name])
    st.session_state.session = session
session.log_path = LOG_FILE if log_enabled else None

if session.turns == 0:
    st.info("Ask anything about programming, for example: *What is a Python list comprehension?*")

for message in session.messages[1:]:  # skip the system prompt
    with st.chat_message(message["role"]):
        render(message["content"])

if question := st.chat_input("Ask a programming question…"):
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer = session.ask(question)
            except Exception as exc:
                st.error(f"The request failed: {exc}")
                st.stop()
        render(answer)
