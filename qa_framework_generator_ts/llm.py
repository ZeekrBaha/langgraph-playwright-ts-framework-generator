from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


class MissingAPIKeyError(RuntimeError):
    """Raised when OPENAI_API_KEY is absent. See .env.example."""


def get_openai_chat_model():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1")
    return ChatOpenAI(model=model_name, api_key=api_key, temperature=0)
