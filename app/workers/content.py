"""Content generation worker for titles, descriptions, and tags."""

from typing import List, Optional
from pydantic import BaseModel
from loguru import logger

from app.config import settings


class VideoContent(BaseModel):
    """Generated video content metadata."""

    title_clickbait: str  # 强吸睛标题
    title_safe: str  # 稳妥标题
    description: str  # 视频描述
    tags: List[str]  # 标签
    keywords: List[str]  # 关键词（用于缩略图）
    summary: str  # 内容摘要


CONTENT_SYSTEM_PROMPT = """你是一位专业的 YouTube 中文频道运营专家，负责为翻译配音后的视频生成元数据。

你的任务是根据视频的原始信息和翻译后的内容，生成吸引中文观众的标题、描述和标签。

要求：
1. 标题要符合中文 YouTube 观众的阅读习惯
2. 使用适当的情绪词和数字来增加点击率
3. 避免直接翻译原标题，要进行本地化改编
4. 标签要包含热门搜索词
5. 描述要包含关键信息并引导观看

输出格式要求（JSON）：
{
  "title_clickbait": "强吸睛标题（使用情绪词、数字、悬念）",
  "title_safe": "稳妥标题（准确描述内容，不夸张）",
  "description": "视频描述（100-200字，包含关键信息和时间戳提示）",
  "tags": ["标签1", "标签2", ...],
  "keywords": ["关键词1", "关键词2", ...],
  "summary": "一句话内容摘要"
}"""


class ContentWorker:
    """Worker for generating video metadata content."""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.translation_model
        self.client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self.client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key required")

            if settings.is_azure_openai:
                from openai import AsyncAzureOpenAI

                # Extract resource URL from base_url
                azure_endpoint = self.base_url.split("/openai/")[0]
                self.client = AsyncAzureOpenAI(
                    api_key=self.api_key,
                    api_version=settings.openai_api_version,
                    azure_endpoint=azure_endpoint,
                )
            else:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )

        return self.client

    async def generate_content(
        self,
        original_title: str,
        original_description: Optional[str],
        transcript_summary: str,
        channel_name: Optional[str] = None,
        video_duration: Optional[float] = None,
    ) -> VideoContent:
        """
        Generate video content metadata.

        Args:
            original_title: Original video title
            original_description: Original video description
            transcript_summary: Summary of translated transcript
            channel_name: Original channel name
            video_duration: Video duration in seconds

        Returns:
            VideoContent with generated metadata
        """
        client = self._get_client()

        # Build context
        duration_str = ""
        if video_duration:
            minutes = int(video_duration // 60)
            duration_str = f"\n视频时长: {minutes} 分钟"

        channel_str = f"\n原频道: {channel_name}" if channel_name else ""

        user_prompt = f"""请为以下翻译配音视频生成中文元数据：

原标题: {original_title}
原描述: {original_description or '无'}
{channel_str}{duration_str}

内容摘要:
{transcript_summary}

请生成适合中文 YouTube 观众的标题、描述和标签。"""

        logger.info("Generating video content metadata...")

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": CONTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        # Parse response
        import json
        content_dict = json.loads(response.choices[0].message.content)

        content = VideoContent(
            title_clickbait=content_dict.get("title_clickbait", ""),
            title_safe=content_dict.get("title_safe", ""),
            description=content_dict.get("description", ""),
            tags=content_dict.get("tags", []),
            keywords=content_dict.get("keywords", []),
            summary=content_dict.get("summary", ""),
        )

        logger.info(f"Generated content: {content.title_safe}")
        return content

    async def generate_transcript_summary(
        self,
        segments: List[dict],
        max_segments: int = 50,
    ) -> str:
        """
        Generate a summary from transcript segments.

        Args:
            segments: List of translated segments
            max_segments: Maximum segments to include

        Returns:
            Summary text
        """
        client = self._get_client()

        # Take evenly distributed segments
        if len(segments) > max_segments:
            step = len(segments) // max_segments
            segments = segments[::step][:max_segments]

        # Build transcript text
        transcript_text = "\n".join(
            f"[{seg.get('speaker', 'SPEAKER')}]: {seg.get('translation', seg.get('text', ''))}"
            for seg in segments
        )

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位内容摘要专家。请用2-3段话概括以下对话/演讲的主要内容和观点。保持客观，突出核心信息。"
                },
                {"role": "user", "content": transcript_text},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        return response.choices[0].message.content.strip()

    async def generate_chapters(
        self,
        segments: List[dict],
        min_chapter_duration: float = 60.0,
    ) -> List[dict]:
        """
        Generate video chapters from transcript.

        Args:
            segments: Translated transcript segments
            min_chapter_duration: Minimum chapter duration in seconds

        Returns:
            List of chapters with timestamps and titles
        """
        client = self._get_client()

        # Group segments into potential chapters
        chapters_text = []
        current_start = 0
        current_texts = []

        for seg in segments:
            current_texts.append(seg.get("translation", seg.get("text", "")))

            if seg["end"] - current_start >= min_chapter_duration:
                chapters_text.append({
                    "start": current_start,
                    "end": seg["end"],
                    "text": " ".join(current_texts),
                })
                current_start = seg["end"]
                current_texts = []

        # Add remaining
        if current_texts:
            chapters_text.append({
                "start": current_start,
                "end": segments[-1]["end"] if segments else current_start,
                "text": " ".join(current_texts),
            })

        # Generate chapter titles
        chapters_prompt = "\n\n".join(
            f"章节 {i+1} ({self._format_timestamp(c['start'])} - {self._format_timestamp(c['end'])}):\n{c['text'][:200]}..."
            for i, c in enumerate(chapters_text)
        )

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "为以下视频章节生成简短的中文标题（每个5-15字）。只返回标题列表，每行一个。"
                },
                {"role": "user", "content": chapters_prompt},
            ],
            temperature=0.5,
        )

        titles = response.choices[0].message.content.strip().split("\n")
        titles = [t.strip().lstrip("0123456789.、）) ") for t in titles if t.strip()]

        # Combine with timestamps
        chapters = []
        for i, chapter in enumerate(chapters_text):
            title = titles[i] if i < len(titles) else f"第 {i+1} 部分"
            chapters.append({
                "timestamp": self._format_timestamp(chapter["start"]),
                "start_seconds": chapter["start"],
                "title": title,
            })

        logger.info(f"Generated {len(chapters)} chapters")
        return chapters

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def format_description_with_chapters(
        self,
        description: str,
        chapters: List[dict],
    ) -> str:
        """
        Format description with chapter timestamps.

        Args:
            description: Base description
            chapters: List of chapters

        Returns:
            Formatted description with chapters
        """
        chapters_text = "\n".join(
            f"{c['timestamp']} {c['title']}"
            for c in chapters
        )

        return f"""{description}

📑 章节目录:
{chapters_text}

---
🎬 本视频由 AI 翻译配音
🔔 订阅频道获取更多优质内容"""
