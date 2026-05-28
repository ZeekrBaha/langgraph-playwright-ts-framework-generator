import os
from unittest.mock import patch

import pytest

from qa_framework_generator_ts.llm import (
    MissingAPIKeyError,
    get_openai_chat_model,
)


def test_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError) as exc:
        get_openai_chat_model()
    assert ".env.example" in str(exc.value)


def test_returns_model_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    model = get_openai_chat_model()
    assert model is not None
