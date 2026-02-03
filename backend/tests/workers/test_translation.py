"""Tests for translation worker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.translation import (
    TranslationWorker,
    MODEL_COSTS,
    TRANSLATION_PROMPTS,
    SUPPORTED_LANGUAGES,
    DEFAULT_TRANSLATION_PROMPT,
)
from app.models.transcript import DiarizedTranscript, DiarizedSegment


class TestModelCosts:
    """Tests for model cost configuration."""

    def test_model_costs_contains_common_models(self):
        """Test that common models are in cost table."""
        assert "gpt-4o" in MODEL_COSTS
        assert "gpt-4o-mini" in MODEL_COSTS
        assert "grok-2" in MODEL_COSTS
        assert "deepseek-chat" in MODEL_COSTS

    def test_model_costs_have_input_output(self):
        """Test that all cost entries have input and output."""
        for model, costs in MODEL_COSTS.items():
            assert "input" in costs, f"Missing input cost for {model}"
            assert "output" in costs, f"Missing output cost for {model}"
            assert costs["input"] >= 0
            assert costs["output"] >= 0

    def test_default_costs_exist(self):
        """Test that default fallback costs exist."""
        assert "default" in MODEL_COSTS


class TestTranslationPrompts:
    """Tests for translation prompts."""

    def test_supported_languages_have_prompts(self):
        """Test that all supported languages have custom prompts."""
        expected_languages = ["zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de"]
        for lang in expected_languages:
            assert lang in TRANSLATION_PROMPTS, f"Missing prompt for {lang}"

    def test_prompts_are_non_empty(self):
        """Test that all prompts have content."""
        for lang, prompt in TRANSLATION_PROMPTS.items():
            assert len(prompt) > 100, f"Prompt for {lang} seems too short"

    def test_chinese_prompts_contain_chinese(self):
        """Test that Chinese prompts are in Chinese."""
        assert "翻译" in TRANSLATION_PROMPTS["zh-CN"] or "翻譯" in TRANSLATION_PROMPTS["zh-TW"]

    def test_default_prompt_has_placeholder(self):
        """Test that default prompt has language placeholder."""
        assert "{language}" in DEFAULT_TRANSLATION_PROMPT


class TestSupportedLanguages:
    """Tests for supported languages configuration."""

    def test_languages_have_display_names(self):
        """Test that all languages have display names."""
        for code, name in SUPPORTED_LANGUAGES.items():
            assert len(code) >= 2
            assert len(name) > 0


class TestTranslationWorker:
    """Tests for TranslationWorker class."""

    def test_get_translation_prompt_known_language(self):
        """Test getting prompt for known language."""
        worker = TranslationWorker()
        prompt = worker._get_translation_prompt("zh-CN")
        assert "简体中文" in prompt

    def test_get_translation_prompt_unknown_language(self):
        """Test getting prompt for unknown language uses default."""
        worker = TranslationWorker()
        prompt = worker._get_translation_prompt("pt-BR")  # Portuguese
        assert "pt-BR" in prompt or "{language}" not in prompt

    def test_calculate_cost_known_model(self):
        """Test cost calculation for known model."""
        worker = TranslationWorker()
        # gpt-4o: $2.50/1M input, $10.00/1M output
        cost = worker._calculate_cost(1000, 500, "gpt-4o")
        expected = (1000 * 2.50 / 1_000_000) + (500 * 10.00 / 1_000_000)
        assert abs(cost - expected) < 0.000001

    def test_calculate_cost_unknown_model_uses_default(self):
        """Test cost calculation for unknown model uses default."""
        worker = TranslationWorker()
        cost = worker._calculate_cost(1000, 500, "unknown-model")
        # Should use default costs
        default_costs = MODEL_COSTS["default"]
        expected = (1000 * default_costs["input"] / 1_000_000) + (
            500 * default_costs["output"] / 1_000_000
        )
        assert abs(cost - expected) < 0.000001

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        worker = TranslationWorker()
        cost = worker._calculate_cost(0, 0, "gpt-4o")
        assert cost == 0.0


class TestTranslationWorkerWithMocks:
    """Tests for TranslationWorker with mocked API calls."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("app.workers.translation.settings") as mock:
            mock.llm_api_key = "test-key"
            mock.llm_base_url = "https://api.test.com/v1"
            mock.llm_model = "gpt-4o"
            mock.is_azure = False
            yield mock

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "翻译后的文本"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.mark.asyncio
    async def test_translate_text_success(self, mock_settings, mock_openai_client):
        """Test successful text translation."""
        worker = TranslationWorker()
        worker.client = mock_openai_client

        result, tokens_in, tokens_out = await worker.translate_text(
            "Hello world", target_language="zh-CN"
        )

        assert result == "翻译后的文本"
        assert tokens_in == 100
        assert tokens_out == 50

    @pytest.mark.asyncio
    async def test_translate_text_empty_response(self, mock_settings, mock_openai_client):
        """Test handling of empty response."""
        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].message.content = None
        mock_openai_client.chat.completions.create.return_value.choices[
            0
        ].finish_reason = "stop"

        worker = TranslationWorker()
        worker.client = mock_openai_client

        result, _, _ = await worker.translate_text("Hello")

        # Should return original text
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_translate_transcript_success(self, mock_settings, mock_openai_client):
        """Test successful transcript translation."""
        worker = TranslationWorker()
        worker.client = mock_openai_client

        transcript = DiarizedTranscript(
            language="en",
            num_speakers=1,
            segments=[
                DiarizedSegment(start=0.0, end=2.0, text="Hello", speaker="SPEAKER_00"),
                DiarizedSegment(start=2.0, end=4.0, text="World", speaker="SPEAKER_00"),
            ],
        )

        result = await worker.translate_transcript(transcript, target_language="zh-CN")

        assert result is not None
        assert len(result.segments) == 2
        assert result.target_language == "zh-CN"
        assert result.source_language == "en"


class TestTranslationWorkerEdgeCases:
    """Tests for edge cases in translation worker."""

    def test_worker_initialization(self):
        """Test worker initializes without API calls."""
        worker = TranslationWorker()
        assert worker.client is None  # Client should be lazy-loaded

    def test_get_translation_prompt_all_supported(self):
        """Test that all supported languages return valid prompts."""
        worker = TranslationWorker()
        for lang_code in SUPPORTED_LANGUAGES.keys():
            prompt = worker._get_translation_prompt(lang_code)
            assert len(prompt) > 50, f"Prompt for {lang_code} is too short"
