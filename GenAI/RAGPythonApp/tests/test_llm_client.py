"""
Unit tests for llm_client.py

The OpenAI client (_client) is mocked in every test so no real API calls
are made and no billing credits are consumed.
"""
import pytest
from unittest.mock import patch, MagicMock

from llm_client import get_answer


# ── Helper ────────────────────────────────────────────────────────────────────

def mock_response(content: str) -> MagicMock:
    """Build a fake OpenAI ChatCompletion response object."""
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


# ── Happy-path tests ──────────────────────────────────────────────────────────

def test_returns_stripped_string():
    """get_answer returns the model content with leading/trailing whitespace removed."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("  The answer.  ")
        result = get_answer("What is ML?", ["Some context."])
    assert result == "The answer."


def test_uses_gpt4o_model():
    """The GPT-4o model is always requested."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("ok")
        get_answer("question", ["context"])
        kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o"


def test_temperature_is_zero():
    """temperature=0 is used to produce deterministic answers."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("ok")
        get_answer("question", ["context"])
        kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["temperature"] == 0


def test_context_chunks_appear_in_user_message():
    """All context chunks are included in the user message sent to GPT-4o."""
    chunks = ["Chunk alpha.", "Chunk beta.", "Chunk gamma."]
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("answer")
        get_answer("my question", chunks)
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]

    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    for chunk in chunks:
        assert chunk in user_msg


def test_question_appears_in_user_message():
    """The user's question is included in the user message."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("answer")
        get_answer("What is gradient descent?", ["Some context."])
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]

    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    assert "What is gradient descent?" in user_msg


def test_system_message_is_present():
    """A system-role message is always included in the messages list."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("answer")
        get_answer("question", ["context"])
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]

    roles = [m["role"] for m in messages]
    assert "system" in roles


def test_system_message_enforces_grounding():
    """The system prompt instructs the model to use only the provided context."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("answer")
        get_answer("question", ["context"])
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]

    system_content = next(m["content"] for m in messages if m["role"] == "system")
    assert "outside knowledge" in system_content.lower() or "context" in system_content.lower()


def test_multiple_chunks_joined_in_message():
    """Multiple chunks are joined into a single user message (not sent as separate calls)."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_response("answer")
        get_answer("question", ["First chunk.", "Second chunk."])
        # Only one API call should be made regardless of chunk count
        assert mock_client.chat.completions.create.call_count == 1


# ── Error-handling tests ──────────────────────────────────────────────────────

def test_api_failure_raises_runtime_error():
    """Any OpenAI API exception is wrapped in a RuntimeError."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.side_effect = Exception("connection timeout")
        with pytest.raises(RuntimeError, match="OpenAI API error"):
            get_answer("question", ["context"])


def test_runtime_error_message_includes_original_error():
    """The RuntimeError message includes the original exception detail."""
    with patch("llm_client._client") as mock_client:
        mock_client.chat.completions.create.side_effect = Exception("quota exceeded")
        with pytest.raises(RuntimeError, match="quota exceeded"):
            get_answer("question", ["context"])
