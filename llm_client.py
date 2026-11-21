"""Create the OpenAI client used by every part of the homework.

Settings come from environment variables, which can be put in a `.env` file:

    OPENAI_API_KEY   the API key (required)
    OPENAI_BASE_URL  optional; set it to use an OpenAI-compatible endpoint
                     such as GitHub Models (https://models.github.ai/inference)
    OPENAI_MODEL     the model name (default: gpt-4o-mini)

The official `openai` package reads OPENAI_API_KEY and OPENAI_BASE_URL itself,
so the same code talks to api.openai.com or to any compatible provider.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent / ".env")

DEFAULT_MODEL = "gpt-4o-mini"


def get_model() -> str:
    return os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL


def make_client() -> OpenAI:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
    # base_url falls back to OPENAI_BASE_URL, then to api.openai.com.
    return OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)
