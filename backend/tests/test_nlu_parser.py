"""
Unit tests for nlu_parser.py — mocking DeepSeek HTTP responses.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.nlu_parser import ParsedTransaction, parse_text_to_transaction


class TestParseTextToTransaction:
    """Tests for the parse_text_to_transaction function."""

    def _make_mock_response(self, content: str) -> MagicMock:
        """Create a properly mocked httpx.Response with a SYNC json() method
        (httpx.Response.json() is synchronous)."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: json.loads(content) if isinstance(content, str) else content
        return mock_resp

    @pytest.mark.asyncio
    async def test_parse_success_first_model(self):
        """Test successful parsing with the first model (GLM-5.2)."""
        mock_response = self._make_mock_response(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "type": "expense",
                                        "amount": 35000,
                                        "category": "Food",
                                        "note": "Makan siang padang",
                                    }
                                )
                            }
                        }
                    ]
                }
            )
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await parse_text_to_transaction("Makan siang 35rb")

            assert result is not None
            assert isinstance(result, ParsedTransaction)
            assert result.type == "expense"
            assert result.amount == Decimal("35000")
            assert result.category == "Food"
            assert result.note == "Makan siang padang"

    @pytest.mark.asyncio
    async def test_parse_single_model_failure_returns_none(self):
        """With a single text model, a failed call returns None. (Multi-model
        fallback is tested at the gateway level in test_llm_client.py.)"""

        async def mock_post_side_effect(*args, **kwargs):
            raise Exception("Model unavailable")

        with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
            result = await parse_text_to_transaction("Gaji 5jt")

            assert result is None

    @pytest.mark.asyncio
    async def test_parse_unrecognized(self):
        """Test parsing returns None for unrecognized input."""
        mock_response = self._make_mock_response(
            json.dumps(
                {"choices": [{"message": {"content": json.dumps({"error": "unrecognized"})}}]}
            )
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await parse_text_to_transaction("Hello world")

            assert result is None

    @pytest.mark.asyncio
    async def test_parse_all_models_fail(self):
        """Test parsing returns None when all models fail."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Network error")

            result = await parse_text_to_transaction("Some text")

            assert result is None

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        """Test parsing handles invalid JSON from LLM."""
        mock_response = self._make_mock_response(
            json.dumps({"choices": [{"message": {"content": "not valid json"}}]})
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await parse_text_to_transaction("Some text")

            assert result is None

    @pytest.mark.asyncio
    async def test_parse_missing_api_key(self):
        """Test parsing returns None when API key is missing."""
        # The key check lives in the LLM gateway (llm_client), not the parser.
        with patch("app.core.llm_client.settings.deepseek_api_key", ""):
            result = await parse_text_to_transaction("Some text")
            assert result is None

    @pytest.mark.asyncio
    async def test_parse_markdown_cleanup(self):
        """Test that markdown code fences are stripped from LLM response."""
        mock_response = self._make_mock_response(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '```json\n{"type": "expense", "amount": 25000, "category": "Transport", "note": "Bensin"}\n```'
                            }
                        }
                    ]
                }
            )
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await parse_text_to_transaction("Bensin 25rb")

            assert result is not None
            assert result.type == "expense"
            assert result.amount == Decimal("25000")
            assert result.category == "Transport"
