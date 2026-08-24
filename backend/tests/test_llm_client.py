"""
Unit tests for llm_client.py — the single LLM gateway (CODING_RULES §2.4).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.llm_client import TEXT_MODELS, _extract_content, call_llm


def _make_response(content: str) -> MagicMock:
    """Mock httpx.Response with a SYNC json() method."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    payload = {"choices": [{"message": {"content": content}}]}
    mock_resp.json = lambda: payload
    return mock_resp


class TestCallLlm:
    @pytest.mark.asyncio
    async def test_returns_raw_content(self):
        """call_llm without a parser returns the raw assistant content."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _make_response('{"type": "expense"}')
            result = await call_llm([{"role": "user", "content": "hello"}], models=TEXT_MODELS)
        assert result == '{"type": "expense"}'

    @pytest.mark.asyncio
    async def test_fallback_chain_on_first_model_failure(self):
        """First model fails → second model is tried with the same messages."""
        calls: list[dict] = []

        async def side_effect(url, headers, json, **kwargs):  # noqa: A002
            calls.append(json)
            if len(calls) == 1:
                raise RuntimeError("model unavailable")
            return _make_response("ok-response")

        with patch("httpx.AsyncClient.post", side_effect=side_effect):
            result = await call_llm(
                [{"role": "user", "content": "hi"}], models=["model-a", "model-b"]
            )
        assert result == "ok-response"
        assert calls[0]["model"] == "model-a"
        assert calls[1]["model"] == "model-b"
        # Same messages forwarded to both models
        assert calls[0]["messages"] == calls[1]["messages"]

    @pytest.mark.asyncio
    async def test_parser_rejection_falls_through_chain(self):
        """If parser returns None, the next model is tried."""
        calls: list[dict] = []
        responses = [_make_response("bad"), _make_response("good")]
        idx = 0

        async def side_effect(url, headers, json, **kwargs):  # noqa: A002
            nonlocal idx
            calls.append(json)
            r = responses[idx]
            idx += 1
            return r

        parser = lambda content: content if content == "good" else None  # noqa: E731

        with patch("httpx.AsyncClient.post", side_effect=side_effect):
            result = await call_llm(
                [{"role": "user", "content": "hi"}],
                models=["model-a", "model-b"],
                parser=parser,
            )
        assert result == "good"
        assert [c["model"] for c in calls] == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_none(self):
        async def side_effect(url, headers, json, **kwargs):  # noqa: A002
            raise RuntimeError("network down")

        with patch("httpx.AsyncClient.post", side_effect=side_effect):
            result = await call_llm([{"role": "user", "content": "hi"}], models=TEXT_MODELS)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_none_without_http(self):
        with patch("app.core.llm_client.settings.deepseek_api_key", ""):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                result = await call_llm([{"role": "user", "content": "hi"}], models=TEXT_MODELS)
        assert result is None
        mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_markdown_fences_stripped(self):
        fenced = '```json\n{"type": "expense"}\n```'
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _make_response(fenced)
            result = await call_llm([{"role": "user", "content": "hi"}], models=TEXT_MODELS)
        assert result == '{"type": "expense"}'


class TestExtractContent:
    def test_strips_json_fences(self):
        assert (
            _extract_content({"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]})
            == '{"a": 1}'
        )

    def test_strips_plain_fences(self):
        assert (
            _extract_content({"choices": [{"message": {"content": "```\nplain\n```"}}]}) == "plain"
        )

    def test_no_fences(self):
        assert _extract_content({"choices": [{"message": {"content": '{"a": 1}'}}]}) == '{"a": 1}'
