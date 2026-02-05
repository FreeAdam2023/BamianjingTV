"""AI-powered RemotionConfig generator service.

Generates Remotion configuration JSON from natural language descriptions.
"""

import json
from typing import Optional, Tuple
from loguru import logger

from app.config import settings
from app.models.creative import (
    RemotionConfig,
    CreativeStyle,
    GlobalConfig,
    AnimationConfig,
    EntranceAnimation,
    ExitAnimation,
    WordHighlightConfig,
    EntranceType,
    ExitType,
    EasingType,
    SubtitlePosition,
    STYLE_PRESETS,
    create_default_config,
)

# Cost per 1M tokens (matches translation.py)
MODEL_COSTS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "grok-2": {"input": 2.00, "output": 10.00},
    "grok-4-fast-non-reasoning": {"input": 2.00, "output": 10.00},
    "grok-beta": {"input": 5.00, "output": 15.00},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "default": {"input": 1.00, "output": 3.00},
}

SYSTEM_PROMPT = """You are a creative subtitle style designer for video content. Your task is to generate a JSON configuration for animated bilingual subtitles based on the user's description.

The configuration schema is:

```json
{
  "version": "1.0",
  "style": "karaoke" | "popup" | "slide" | "typewriter" | "custom",
  "global": {
    "fontFamily": "string (CSS font-family)",
    "backgroundColor": "string (hex color like #1a2744)",
    "subtitlePosition": "bottom" | "top" | "center",
    "enFontSize": number (pixels, typically 24-48),
    "zhFontSize": number (pixels, typically 24-48),
    "enColor": "string (hex color)",
    "zhColor": "string (hex color)",
    "fontWeight": "string (400, 500, 600, 700)",
    "lineSpacing": number (pixels, typically 4-16)
  },
  "animation": {
    "entrance": {
      "type": "fadeIn" | "slideIn" | "bounce" | "typewriter" | "none",
      "duration": number (frames at 30fps, typically 8-20),
      "easing": "linear" | "easeIn" | "easeOut" | "easeInOut" | "spring"
    },
    "wordHighlight": {
      "enabled": boolean,
      "color": "string (hex color for highlighted word)",
      "scale": number (e.g., 1.1 for 10% larger),
      "duration": number (frames, how long each word stays highlighted)
    } | null,
    "exit": {
      "type": "fadeOut" | "slideOut" | "none",
      "duration": number (frames at 30fps),
      "easing": "linear" | "easeIn" | "easeOut" | "easeInOut"
    }
  }
}
```

Style presets:
- **karaoke**: Words highlight one-by-one as they're spoken (YouTube lyric videos). Use wordHighlight.
- **popup**: Subtitles bounce in with a spring effect (energetic content).
- **slide**: Subtitles slide in from the side smoothly (professional look).
- **typewriter**: Characters appear one by one (narrative/documentary style).
- **custom**: Mix and match settings.

Guidelines:
1. Parse the user's intent and map it to appropriate settings.
2. For color requests like "yellow highlight", use appropriate hex codes (#facc15 for yellow, etc.).
3. For animation speed: "fast" = 8-10 frames, "normal" = 12-15 frames, "slow" = 18-25 frames.
4. If user mentions a style name (karaoke, popup, etc.), use that as the base style.
5. Always output valid JSON only, no explanations in the JSON.
6. After the JSON, provide a brief explanation of what you configured.

Output format:
```json
{config}
```
Explanation: [brief description of the configuration]"""


class CreativeConfigGenerator:
    """AI-powered Remotion config generator."""

    def __init__(self):
        """Initialize the generator."""
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.client = None

    def _get_client(self):
        """Get or create LLM client."""
        if self.client is None:
            if not self.api_key:
                raise ValueError(
                    "LLM API key required. Set LLM_API_KEY environment variable."
                )

            if settings.is_azure:
                from openai import AsyncAzureOpenAI

                azure_endpoint = self.base_url.split("/openai/")[0]
                self.client = AsyncAzureOpenAI(
                    api_key=self.api_key,
                    api_version=settings.azure_api_version,
                    azure_endpoint=azure_endpoint,
                )
            else:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )

        return self.client

    def _calculate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost for API call based on token usage."""
        cost_entry = MODEL_COSTS.get(self.model, MODEL_COSTS["default"])
        cost = (tokens_in * cost_entry["input"] / 1_000_000) + (
            tokens_out * cost_entry["output"] / 1_000_000
        )
        return round(cost, 6)

    def _build_user_prompt(
        self,
        prompt: str,
        style_preset: Optional[CreativeStyle] = None,
        previous_config: Optional[RemotionConfig] = None,
    ) -> str:
        """Build the user prompt with context."""
        parts = []

        # Add style preset hint
        if style_preset:
            parts.append(f"Base style: {style_preset.value}")

        # Add previous config for iteration
        if previous_config:
            parts.append(f"Current config (modify based on request):\n```json\n{previous_config.model_dump_json(by_alias=True, indent=2)}\n```")

        # Add user's request
        parts.append(f"User request: {prompt}")

        return "\n\n".join(parts)

    def _parse_response(self, content: str) -> Tuple[RemotionConfig, str]:
        """Parse the LLM response to extract config and explanation."""
        # Try to extract JSON from markdown code blocks
        json_str = None
        explanation = ""

        if "```json" in content:
            try:
                start = content.index("```json") + 7
                end = content.index("```", start)
                json_str = content[start:end].strip()
                # Get explanation after the JSON block
                remaining = content[end + 3:].strip()
                if remaining.startswith("Explanation:"):
                    explanation = remaining[12:].strip()
                elif remaining:
                    explanation = remaining
            except (ValueError, IndexError):
                pass

        # Fallback: try to parse the whole content as JSON
        if not json_str:
            try:
                # Find first { and last }
                start = content.index("{")
                end = content.rindex("}") + 1
                json_str = content[start:end]
            except ValueError:
                raise ValueError("Could not find JSON in response")

        # Parse JSON
        try:
            config_dict = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}")

        # Convert to RemotionConfig
        try:
            config = RemotionConfig.model_validate(config_dict)
        except Exception as e:
            logger.warning(f"Config validation failed, using defaults: {e}")
            # Fall back to default config with detected style
            style = config_dict.get("style", "karaoke")
            try:
                style_enum = CreativeStyle(style)
            except ValueError:
                style_enum = CreativeStyle.KARAOKE
            config = create_default_config(style_enum)

        return config, explanation

    async def generate(
        self,
        prompt: str,
        style_preset: Optional[CreativeStyle] = None,
        previous_config: Optional[RemotionConfig] = None,
    ) -> Tuple[RemotionConfig, str, int, float]:
        """Generate RemotionConfig from natural language.

        Args:
            prompt: User's description of desired subtitle style
            style_preset: Optional base style to start from
            previous_config: Optional previous config for iterative refinement

        Returns:
            Tuple of (config, explanation, tokens_used, cost_usd)
        """
        client = self._get_client()

        user_prompt = self._build_user_prompt(prompt, style_preset, previous_config)

        try:
            if settings.is_azure:
                response = await client.chat.completions.create(
                    model=settings.azure_deployment_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                )
            else:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                )

            content = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0
            tokens_total = tokens_in + tokens_out
            cost = self._calculate_cost(tokens_in, tokens_out)

            config, explanation = self._parse_response(content)

            logger.info(
                f"Generated creative config: style={config.style}, "
                f"tokens={tokens_total}, cost=${cost:.4f}"
            )

            return config, explanation, tokens_total, cost

        except Exception as e:
            logger.error(f"Failed to generate config: {e}")
            # Fall back to default config
            style = style_preset or CreativeStyle.KARAOKE
            return (
                create_default_config(style),
                f"Using default {style.value} style (AI generation failed: {str(e)})",
                0,
                0.0,
            )

    async def close(self):
        """Close the client connection."""
        if self.client:
            await self.client.close()
            self.client = None
