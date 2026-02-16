"""Thumbnail generation worker for YouTube-style video covers.

Uses video screenshots (not AI-generated images) for authenticity.
"""

import hashlib
import httpx
import io
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
from loguru import logger

from app.config import settings

# YouTube thumbnail dimensions
YOUTUBE_WIDTH = 1280
YOUTUBE_HEIGHT = 720


class ThumbnailWorker:
    """Worker for generating YouTube-style video thumbnails from video frames."""

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.enabled = bool(self.api_key)

    async def analyze_emotional_moments(
        self,
        subtitles: List[dict],
    ) -> Tuple[float, str]:
        """Analyze subtitles to find the most dramatic/emotional moment.

        Args:
            subtitles: List of subtitle dicts with 'start', 'end', 'en' keys

        Returns:
            Tuple of (timestamp, reason) for the most eye-catching moment
        """
        # Format subtitles for analysis
        subtitle_text = "\n".join([
            f"[{s.get('start', 0):.1f}s] {s.get('en', s.get('text', ''))}"
            for s in subtitles[:50]  # Analyze first 50 segments
        ])

        system_prompt = """你是一个视频封面设计专家。分析视频台词，找出最适合做封面的那一刻。

寻找以下类型的时刻：
- 冲突、对抗、争论
- 震惊、惊讶的反应
- 重要宣布、声明
- 情绪激动的表达
- 有争议性的言论

返回JSON格式：
{"timestamp": 秒数, "reason": "为什么选这个时刻"}

只输出JSON，不要其他内容。"""

        user_prompt = f"""分析以下台词，找出最适合做YouTube封面的时刻：

{subtitle_text}

选择最博眼球、最有冲击力的那一刻："""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 150,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                result = json.loads(content)
                timestamp = float(result.get("timestamp", 10))
                reason = result.get("reason", "")

                logger.info(f"Selected moment at {timestamp}s: {reason}")
                return timestamp, reason

        except Exception as e:
            logger.error(f"Failed to analyze emotional moments: {e}")
            # Default to 10 seconds into the video
            return 10.0, "Default selection"

    async def generate_clickbait_title(
        self,
        title: str,
        subtitles: List[dict],
    ) -> Tuple[str, str]:
        """Generate clickbait Chinese titles for thumbnail.

        Args:
            title: Video title
            subtitles: List of subtitle dicts

        Returns:
            Tuple of (main_title, sub_title) in Chinese
        """
        content_sample = " ".join([
            s.get('en', s.get('text', '')) for s in subtitles[:15]
        ])[:800]

        system_prompt = """你是一个优秀的中文标题撰写者，为YouTube学习频道制作封面标题。

## 核心原则：
1. **忠实内容**：标题必须准确反映视频真实主题，不歪曲、不臆造
2. **简洁有力**：用最少的字传达最核心的信息
3. **自然好奇**：通过内容本身的看点吸引观众，而非情绪煽动
4. **人名/专有名词**：如有明确的人物或事件，直接点明

## 标题技巧：
- 提炼视频最核心的一个观点或事件
- 如果内容有天然的反差或新意，如实呈现即可
- 可用问句制造适度好奇，但问题必须是视频真正回答的
- 避免使用"震怒、崩溃、气炸、曝光"等夸张情绪词

## 输出要求：
- 主标题：6-12字，准确概括核心内容
- 副标题：6-14字，补充关键信息或点明看点
- 使用简体中文

## 示例：
主标题：马斯克谈AI的未来
副标题：为什么他认为监管迫在眉睫

主标题：为什么美国人不坐高铁
副标题：一个你想不到的原因

主标题：比尔盖茨的阅读方法
副标题：每年50本书是怎么做到的

只输出JSON格式：
{"main": "主标题", "sub": "副标题"}"""

        user_prompt = f"""视频标题：{title}

视频内容摘要：{content_sample}

生成准确且吸引人的中文封面标题："""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 200,
                        "temperature": 0.6,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                titles = json.loads(content)
                return titles.get("main", "精彩内容"), titles.get("sub", "不容错过")

        except Exception as e:
            logger.error(f"Failed to generate clickbait title: {e}")
            return "精彩内容", "不容错过"

    async def generate_youtube_metadata(
        self,
        title: str,
        subtitles: List[dict],
        source_url: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> dict:
        """Generate SEO-optimized YouTube metadata (title, description, tags).

        Args:
            title: Original video title
            subtitles: List of subtitle dicts
            source_url: Original video URL
            duration: Video duration in seconds

        Returns:
            Dict with 'title', 'description', 'tags' keys
        """
        # Sample content from entire video for better understanding
        total_segments = len(subtitles)
        max_content_segments = 50

        if total_segments <= max_content_segments:
            content_subtitles = subtitles
        else:
            step = total_segments / max_content_segments
            content_subtitles = [subtitles[int(i * step)] for i in range(max_content_segments)]

        content_sample = " ".join([
            s.get('en', s.get('text', '')) for s in content_subtitles
        ])[:2000]

        # Format duration for description
        duration_str = ""
        if duration:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            if hours > 0:
                duration_str = f"{hours}小时{minutes}分钟"
            else:
                duration_str = f"{minutes}分钟"

        system_prompt = """你是一个YouTube SEO专家。根据视频内容生成能最大化曝光量的元数据。

**任务：生成YouTube SEO优化的标题、描述和标签**

## 标题规则：
- 长度：40-70个字符（中文约20-35字）
- 使用简体中文
- 包含核心关键词
- 吸引点击但不虚假
- 可加入数字、问号、惊叹号增加吸引力
- 示例：「川普2025新政策震惊全球！专家解读5大影响」

## 描述规则：
- 第一行：核心内容摘要（会显示在搜索结果）
- 包含3-5个核心关键词
- 添加时间戳（如果可能）
- 包含行动号召（订阅、点赞、评论）
- 添加相关 #hashtag
- 使用简体中文
- 长度：200-500字

## 标签规则：
- 15-25个相关标签
- 混合：核心关键词 + 长尾关键词 + 热门话题
- 使用简体中文和英文标签
- 避免无关标签

输出JSON格式：
{
  "title": "SEO优化的标题",
  "description": "完整的描述（包含hashtag）",
  "tags": ["标签1", "标签2", "标签3", ...]
}

只输出JSON，不要其他内容。"""

        user_prompt = f"""原视频标题：{title}

视频内容摘要：
{content_sample}

{f"视频时长：{duration_str}" if duration_str else ""}
{f"原始链接：{source_url}" if source_url else ""}

请生成SEO优化的YouTube元数据："""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 1500,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                result = json.loads(content)
                logger.info(f"Generated YouTube metadata: title={result.get('title', '')[:30]}...")
                return {
                    "title": result.get("title", title),
                    "description": result.get("description", f"Original: {source_url or 'N/A'}"),
                    "tags": result.get("tags", ["learning", "english", "chinese"]),
                }

        except Exception as e:
            logger.error(f"Failed to generate YouTube metadata: {e}")
            return {
                "title": title,
                "description": f"Original: {source_url or 'N/A'}",
                "tags": ["learning", "english", "chinese"],
            }

    async def generate_unified_metadata(
        self,
        title: str,
        subtitles: List[dict],
        source_url: Optional[str] = None,
        duration: Optional[float] = None,
        num_title_candidates: int = 5,
        user_instruction: Optional[str] = None,
    ) -> dict:
        """Generate coordinated YouTube metadata and thumbnail title candidates together.

        This ensures the YouTube title and thumbnail titles are consistent and
        follow the same user instruction.

        Args:
            title: Original video title
            subtitles: List of subtitle dicts
            source_url: Original video URL
            duration: Video duration in seconds
            num_title_candidates: Number of thumbnail title candidates
            user_instruction: Optional user instruction to guide generation

        Returns:
            Dict with 'youtube' (title, description, tags) and 'thumbnail_candidates' (list)
        """
        # Sample content from entire video for better understanding
        total_segments = len(subtitles)
        max_content_segments = 50  # More segments for content understanding

        if total_segments <= max_content_segments:
            content_subtitles = subtitles
        else:
            # Sample evenly across the video for content understanding
            step = total_segments / max_content_segments
            content_subtitles = [subtitles[int(i * step)] for i in range(max_content_segments)]

        content_sample = " ".join([
            s.get('en', s.get('text', '')) for s in content_subtitles
        ])[:2000]  # Increased limit for longer videos

        # Format duration for description
        duration_str = ""
        if duration:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            if hours > 0:
                duration_str = f"{hours}小时{minutes}分钟"
            else:
                duration_str = f"{minutes}分钟"

        # Log the instruction for debugging
        if user_instruction:
            logger.info(f"Generating metadata with user instruction: {user_instruction}")
        else:
            logger.info("Generating metadata without user instruction")

        # Build instruction section - placed prominently in user prompt for better adherence
        instruction_block = ""
        if user_instruction:
            instruction_block = f"""
⚠️ **用户创作指导 - 最高优先级，必须严格遵循！** ⚠️
「{user_instruction}」

你必须根据上述指导来创作内容。标题和描述必须围绕用户指定的主题/角度。
如果用户指定了"突出冲突"，标题必须体现冲突；如果指定了"某个话题"，必须以该话题为核心。
---

"""

        system_prompt = f"""你是一个专业的中文YouTube标题和元数据撰写者，为学习类频道制作准确、吸引人的内容。

**核心原则：忠实于视频原意，用内容本身的价值吸引观众。**
**重要：YouTube标题和封面标题必须主题一致、风格协调！**

## 标题撰写原则：
1. **准确第一**：标题必须如实反映视频核心内容，不歪曲、不臆造
2. **提炼精华**：找到视频最有价值、最有看点的一个核心信息
3. **自然好奇**：如果内容本身有新意、反差或独特视角，如实呈现即可
4. **简洁有力**：少用形容词，多用具体名词和动词
5. **避免煽情**：不使用"震怒、崩溃、气炸、曝光"等夸张情绪词

## 任务1：YouTube元数据

### 标题规则：
- 长度：40-70个字符（中文约20-35字）
- 使用简体中文
- 准确概括视频核心内容
- 如有具体人物或事件，直接点明
- 可用问句制造适度好奇，但问题必须是视频真正回答的
- 示例：「马斯克解释为什么SpaceX不怕火箭爆炸｜完整访谈」

### 描述规则：
- 使用简体中文
- **必须包含智能时间线章节标记**，格式如下：
  ⏰ 时间线
  00:00 开场白
  02:30 第一个重点
  05:45 第二个重点
  ...

**⚠️ 时间线章节生成规则（最重要！）：**
1. **根据内容主题变化划分章节**，不是按固定时间间隔切分
2. 识别主要话题转换点：新话题引入、重要观点、关键问答等
3. **章节数量控制在 8-12 个**（最多不超过 15 个），只保留最重要的节点
4. 每个章节标题要简洁有力（4-10字），概括核心内容
5. **章节必须均匀覆盖整个视频**，从开头到结尾

- **结构要求**：
  1. 第一段：核心内容摘要（2-3句话，客观概括）
  2. 第二段：时间线（⏰标记，根据内容主题智能划分）
  3. 第三段：关键词标签（#hashtag格式）
  4. 第四段：行动号召（订阅、点赞、开启小铃铛）
  5. 最后必须包含：
     ---
     📺 原视频：{{source_url}}
     ⚠️ 本视频仅供学习交流使用，版权归原作者所有。如有侵权请联系删除。
- 长度：400-800字

### 标签规则：
- 15-25个相关标签
- 混合简体中文和英文

## 任务2：封面标题候选（{num_title_candidates}组）

### 每组包含：
- main: 主标题（6-12字，准确概括核心内容）
- sub: 副标题（6-14字，补充关键信息或点明看点）
- style: 风格描述

### 五种风格：
1. **概括型**：直接点明主题，如「马斯克谈AI的未来」
2. **悬念型**：用问句引发好奇，如「他为什么放弃百万年薪？」
3. **观点型**：突出核心论点，如「读书没用？他用亲身经历反驳」
4. **故事型**：强调叙事性，如「从破产到亿万富翁的十年」
5. **发现型**：分享新知，如「原来英语有这个规律」

### 规则：
- 使用简体中文
- **必须与YouTube标题主题一致**
- 标题要让人觉得"这个内容值得看"，而非"不点开会后悔"

输出JSON格式：
{{
  "youtube": {{
    "title": "YouTube标题",
    "description": "完整描述",
    "tags": ["标签1", "标签2", ...]
  }},
  "thumbnail_candidates": [
    {{"main": "主标题1", "sub": "副标题1", "style": "震撼型"}},
    {{"main": "主标题2", "sub": "副标题2", "style": "悬念型"}},
    ...
  ]
}}

只输出JSON，不要其他内容。"""

        # Format subtitles with timestamps for intelligent chapter detection
        # Strategy: compress subtitles into time blocks for better topic detection
        total_segments = len(subtitles)
        video_duration_minutes = int((duration or 0) / 60) if duration else total_segments // 6

        # Group subtitles into ~1 minute blocks for topic detection
        # Each block shows the timestamp and condensed content
        time_blocks = []
        block_duration = 60  # seconds per block

        current_block_start = 0
        current_block_texts = []

        for s in subtitles:
            seg_start = s.get('start', 0)
            seg_text = s.get('en', s.get('text', ''))

            # Check if we've moved to a new time block
            if seg_start >= current_block_start + block_duration and current_block_texts:
                # Save current block
                minutes = int(current_block_start // 60)
                seconds = int(current_block_start % 60)
                block_summary = ' '.join(current_block_texts)[:150]  # Condensed
                time_blocks.append(f"[{minutes:02d}:{seconds:02d}] {block_summary}")

                # Start new block
                current_block_start = (seg_start // block_duration) * block_duration
                current_block_texts = []

            current_block_texts.append(seg_text[:50])

        # Don't forget the last block
        if current_block_texts:
            minutes = int(current_block_start // 60)
            seconds = int(current_block_start % 60)
            block_summary = ' '.join(current_block_texts)[:150]
            time_blocks.append(f"[{minutes:02d}:{seconds:02d}] {block_summary}")

        subtitle_timeline = "\n".join(time_blocks)

        logger.info(f"Grouped {total_segments} subtitles into {len(time_blocks)} time blocks for chapter detection")

        user_prompt = f"""{instruction_block}原视频标题：{title}

{f"**视频总时长：{duration_str}** （章节必须均匀覆盖从 00:00 到结尾）" if duration_str else ""}
{f"原始链接（必须包含在描述最后）：{source_url}" if source_url else ""}

**视频内容时间块**（每分钟一块，用于识别话题变化）：
{subtitle_timeline}

**时间线要求：识别 8-12 个最重要的主题转换点作为章节（不要超过15个）**
- 覆盖整个视频（从开头到结尾）
- 基于内容主题变化划分
- 章节标题简洁有力（4-10字）

视频内容摘要：
{content_sample}

请生成协调一致的YouTube元数据和{num_title_candidates}组封面标题候选。
**描述中必须包含智能时间线章节（根据话题变化划分，覆盖整个视频）、原视频链接、版权声明！**
{f" **请务必围绕用户指导「{user_instruction}」来创作！**" if user_instruction else ""}"""

        # Lower temperature when user provides instruction for better adherence
        temperature = 0.5 if user_instruction else 0.6

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 3000,  # Increased for longer timeline with more chapters
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                result = json.loads(content)

                # Format thumbnail candidates
                candidates = []
                for i, c in enumerate(result.get("thumbnail_candidates", [])[:num_title_candidates]):
                    candidates.append({
                        "index": i,
                        "main": c.get("main", "精彩内容"),
                        "sub": c.get("sub", "不容错过"),
                        "style": c.get("style", ""),
                    })

                youtube = result.get("youtube", {})
                logger.info(f"Generated unified metadata: YouTube title={youtube.get('title', '')[:30]}...")

                return {
                    "youtube": {
                        "title": youtube.get("title", title),
                        "description": youtube.get("description", f"Original: {source_url or 'N/A'}"),
                        "tags": youtube.get("tags", ["learning", "english", "chinese"]),
                    },
                    "thumbnail_candidates": candidates,
                }

        except Exception as e:
            logger.error(f"Failed to generate unified metadata: {e}")
            # Return defaults
            return {
                "youtube": {
                    "title": title,
                    "description": f"Original: {source_url or 'N/A'}",
                    "tags": ["learning", "english", "chinese"],
                },
                "thumbnail_candidates": [
                    {"index": 0, "main": "精彩内容", "sub": "不容错过", "style": "默认"},
                ],
            }

    async def generate_title_candidates(
        self,
        title: str,
        subtitles: List[dict],
        num_candidates: int = 5,
        user_instruction: Optional[str] = None,
    ) -> List[dict]:
        """Generate multiple title candidates for user selection.

        Args:
            title: Video title
            subtitles: List of subtitle dicts
            num_candidates: Number of candidates to generate
            user_instruction: Optional user instruction to guide title generation

        Returns:
            List of dicts with 'main' and 'sub' keys
        """
        content_sample = " ".join([
            s.get('en', s.get('text', '')) for s in subtitles[:20]
        ])[:1000]

        # Build instruction section - make it prominent if provided
        instruction_section = ""
        user_instruction_reminder = ""
        if user_instruction:
            instruction_section = f"""
**【用户创作指导 - 必须遵循】**
{user_instruction}
---
"""
            user_instruction_reminder = f"\n\n**重要：标题必须围绕用户指导「{user_instruction}」来创作！**"

        system_prompt = f"""你是一个专业的中文YouTube封面标题撰写者。生成{num_candidates}组准确、吸引人的标题。
{instruction_section}

## 核心原则：
1. **忠实内容**：标题必须准确反映视频真实主题，不歪曲、不臆造
2. **提炼精华**：找到视频最有价值的核心信息
3. **自然好奇**：用内容本身的看点吸引观众，而非情绪煽动
4. **简洁有力**：少用形容词，多用具体名词和动词
5. **避免煽情**：不使用"震怒、崩溃、气炸、曝光"等夸张情绪词

## 标题技巧：
- 提炼视频最核心的一个观点或事件
- 如有天然的反差或新意，如实呈现
- 可用问句制造适度好奇，但问题必须是视频真正回答的
- 具体人名、数字比笼统描述更好

## 输出要求：
- 主标题：6-12字，准确概括核心内容
- 副标题：6-14字，补充关键信息或点明看点
- 使用简体中文

## 五种风格：
1. 概括型：直接点明主题（「马斯克谈AI的未来」）
2. 悬念型：用问句引发好奇（「他为什么放弃百万年薪？」）
3. 观点型：突出核心论点（「读书没用？他用亲身经历反驳」）
4. 故事型：强调叙事性（「从破产到亿万富翁的十年」）
5. 发现型：分享新知（「原来英语有这个规律」）

输出JSON数组格式：
[
  {{"main": "主标题1", "sub": "副标题1", "style": "风格描述"}},
  {{"main": "主标题2", "sub": "副标题2", "style": "风格描述"}},
  ...
]"""

        user_prompt = f"""视频标题：{title}

视频内容摘要：{content_sample}

生成{num_candidates}组不同风格的封面标题：{user_instruction_reminder}"""

        # Lower temperature when user provides instruction for better adherence
        temperature = 0.5 if user_instruction else 0.7

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 800,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                candidates = json.loads(content)

                # Ensure we have the required fields
                result = []
                for i, c in enumerate(candidates[:num_candidates]):
                    result.append({
                        "index": i,
                        "main": c.get("main", "精彩内容"),
                        "sub": c.get("sub", "不容错过"),
                        "style": c.get("style", ""),
                    })

                logger.info(f"Generated {len(result)} title candidates")
                return result

        except Exception as e:
            logger.error(f"Failed to generate title candidates: {e}")
            # Return default candidates
            return [
                {"index": 0, "main": "精彩内容", "sub": "不容错过", "style": "默认"},
            ]

    def get_video_duration(self, video_path: Path) -> Optional[float]:
        """Get video duration in seconds using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds or None if failed
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
        return None

    def extract_candidate_frames(
        self,
        video_path: Path,
        output_dir: Path,
        num_candidates: int = 6,
        duration: Optional[float] = None,
    ) -> List[dict]:
        """Extract multiple candidate frames at different timestamps.

        Args:
            video_path: Path to video file
            output_dir: Directory to save frames
            num_candidates: Number of candidates to generate (default 6)
            duration: Video duration (will be auto-detected if not provided)

        Returns:
            List of dicts with 'timestamp', 'path', 'filename', 'url' keys
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if duration is None:
            duration = self.get_video_duration(video_path)
            if duration is None:
                logger.error("Could not determine video duration")
                return []

        # Generate timestamps at evenly distributed points (avoiding very start/end)
        # e.g., for 6 candidates: 10%, 25%, 40%, 55%, 70%, 85%
        candidates = []
        for i in range(num_candidates):
            pct = 0.10 + (i * 0.75 / (num_candidates - 1))  # 10% to 85%
            timestamp = duration * pct

            filename = f"candidate_{i+1}_{int(timestamp)}s.jpg"
            output_path = output_dir / filename

            result = self.extract_frame(video_path, timestamp, output_path)
            if result:
                candidates.append({
                    "index": i + 1,
                    "timestamp": round(timestamp, 2),
                    "path": str(output_path),
                    "filename": filename,
                })
                logger.info(f"Extracted candidate {i+1} at {timestamp:.1f}s")

        return candidates

    def extract_frame(
        self,
        video_path: Path,
        timestamp: float,
        output_path: Path,
    ) -> Optional[Path]:
        """Extract a frame from video at given timestamp.

        Args:
            video_path: Path to video file
            timestamp: Time in seconds
            output_path: Where to save the frame

        Returns:
            Path to extracted frame or None if failed
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",  # High quality JPEG
            "-y",  # Overwrite
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return None

            if output_path.exists():
                logger.info(f"Extracted frame at {timestamp}s: {output_path}")
                return output_path
            else:
                logger.error("Frame extraction completed but file not found")
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            return None
        except Exception as e:
            logger.exception(f"Failed to extract frame: {e}")
            return None

    def add_text_overlay(
        self,
        image_path: Path,
        main_title: str,
        sub_title: str,
    ) -> bytes:
        """Add text overlays to the thumbnail image.

        Args:
            image_path: Path to base image
            main_title: Main title (yellow text)
            sub_title: Sub title (white text on blue bar)

        Returns:
            Final image bytes (with "中英字幕" badge in top-left)
        """
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance
        import os

        # Load and resize image
        img = Image.open(image_path)
        img = img.resize((YOUTUBE_WIDTH, YOUTUBE_HEIGHT), Image.Resampling.LANCZOS)

        # Slightly increase contrast for more dramatic look
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.1)

        draw = ImageDraw.Draw(img)

        # Try to load Chinese font
        font_paths = [
            # Docker / Ubuntu (fonts-noto-cjk package)
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            # Windows
            "C:\\Windows\\Fonts\\msyh.ttc",
            "C:\\Windows\\Fonts\\simhei.ttf",
        ]

        def load_font(size: int) -> ImageFont.FreeTypeFont:
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except Exception:
                        continue
            return ImageFont.load_default()

        def get_font_to_fit(text: str, max_width: int, max_size: int, min_size: int = 40) -> ImageFont.FreeTypeFont:
            """Find the largest font size that fits the text within max_width."""
            for size in range(max_size, min_size - 1, -5):
                font = load_font(size)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                if text_width <= max_width:
                    return font
            return load_font(min_size)

        # Calculate available width with padding
        padding = 40  # 20px on each side
        available_width = YOUTUBE_WIDTH - padding * 2

        # Fonts - dynamically sized to fit
        main_font = get_font_to_fit(main_title, available_width, max_size=140, min_size=60)
        sub_font = get_font_to_fit(sub_title, available_width, max_size=100, min_size=40)
        badge_font = load_font(42)

        # Colors
        yellow = (255, 255, 0)
        white = (255, 255, 255)
        blue = (0, 120, 200)
        black_outline = (0, 0, 0)

        def draw_text_with_outline(
            draw: ImageDraw.Draw,
            position: Tuple[int, int],
            text: str,
            font: ImageFont.FreeTypeFont,
            fill_color: Tuple[int, int, int],
            outline_color: Tuple[int, int, int] = black_outline,
            outline_width: int = 3,
        ):
            """Draw text with outline for better visibility."""
            x, y = position
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
            draw.text(position, text, font=font, fill=fill_color)

        # Draw main title (yellow, center area - large and impactful)
        main_bbox = draw.textbbox((0, 0), main_title, font=main_font)
        main_width = main_bbox[2] - main_bbox[0]
        main_height = main_bbox[3] - main_bbox[1]
        main_x = (YOUTUBE_WIDTH - main_width) // 2
        main_y = YOUTUBE_HEIGHT - 300  # Higher position for larger text

        draw_text_with_outline(draw, (main_x, main_y), main_title, main_font, yellow, outline_width=6)

        # Draw blue bar at bottom (taller for larger text)
        bar_height = 130
        bar_y = YOUTUBE_HEIGHT - bar_height
        draw.rectangle([(0, bar_y), (YOUTUBE_WIDTH, YOUTUBE_HEIGHT)], fill=blue)

        # Draw sub title (white on blue bar)
        sub_bbox = draw.textbbox((0, 0), sub_title, font=sub_font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        sub_x = (YOUTUBE_WIDTH - sub_width) // 2
        sub_y = bar_y + (bar_height - (sub_bbox[3] - sub_bbox[1])) // 2 - 8

        draw.text((sub_x, sub_y), sub_title, font=sub_font, fill=white)

        # Draw corner badge (top-left) - two lines: "中英" / "字幕"
        badge_line1 = "中英"
        badge_line2 = "字幕"
        badge_padding_x = 16
        badge_padding_y = 12
        line_spacing = 6

        bbox1 = draw.textbbox((0, 0), badge_line1, font=badge_font)
        bbox2 = draw.textbbox((0, 0), badge_line2, font=badge_font)
        line1_width = bbox1[2] - bbox1[0]
        line2_width = bbox2[2] - bbox2[0]
        line_height = bbox1[3] - bbox1[1]

        badge_width = max(line1_width, line2_width) + badge_padding_x * 2
        badge_height = line_height * 2 + line_spacing + badge_padding_y * 2

        draw.rectangle([(20, 20), (20 + badge_width, 20 + badge_height)], fill=yellow)
        # Center each line horizontally
        line1_x = 20 + (badge_width - line1_width) // 2
        line2_x = 20 + (badge_width - line2_width) // 2
        draw.text((line1_x, 20 + badge_padding_y), badge_line1, font=badge_font, fill=(0, 0, 0))
        draw.text((line2_x, 20 + badge_padding_y + line_height + line_spacing), badge_line2, font=badge_font, fill=(0, 0, 0))

        # Draw corner badge (top-right) - two lines: "知识" / "卡片"
        r_line1 = "知识"
        r_line2 = "卡片"
        r_bbox1 = draw.textbbox((0, 0), r_line1, font=badge_font)
        r_bbox2 = draw.textbbox((0, 0), r_line2, font=badge_font)
        r_line1_w = r_bbox1[2] - r_bbox1[0]
        r_line2_w = r_bbox2[2] - r_bbox2[0]
        r_line_h = r_bbox1[3] - r_bbox1[1]

        r_badge_w = max(r_line1_w, r_line2_w) + badge_padding_x * 2
        r_badge_h = r_line_h * 2 + line_spacing + badge_padding_y * 2
        r_x = YOUTUBE_WIDTH - 20 - r_badge_w

        draw.rectangle([(r_x, 20), (r_x + r_badge_w, 20 + r_badge_h)], fill=yellow)
        draw.text((r_x + (r_badge_w - r_line1_w) // 2, 20 + badge_padding_y), r_line1, font=badge_font, fill=(0, 0, 0))
        draw.text((r_x + (r_badge_w - r_line2_w) // 2, 20 + badge_padding_y + r_line_h + line_spacing), r_line2, font=badge_font, fill=(0, 0, 0))

        # Save to bytes
        output = io.BytesIO()
        img.save(output, format="PNG", quality=95)
        return output.getvalue()

    async def generate_from_frame(
        self,
        title: str,
        subtitles: List[dict],
        frame_path: Path,
        output_dir: Path,
        filename: Optional[str] = None,
        main_title: Optional[str] = None,
        sub_title: Optional[str] = None,
    ) -> Optional[Path]:
        """Generate thumbnail from an existing frame image.

        Args:
            title: Video title (used for generating titles if not provided)
            subtitles: List of subtitle dicts (used for generating titles if not provided)
            frame_path: Path to source frame image
            output_dir: Directory to save thumbnail
            filename: Optional filename
            main_title: Optional pre-generated main title
            sub_title: Optional pre-generated sub title

        Returns:
            Path to generated thumbnail or None
        """
        frame_path = Path(frame_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not frame_path.exists():
            logger.error(f"Frame not found: {frame_path}")
            return None

        # Generate titles if not provided
        if not main_title or not sub_title:
            if self.enabled:
                logger.info("Generating clickbait titles...")
                main_title, sub_title = await self.generate_clickbait_title(title, subtitles)
            else:
                main_title = main_title or "精彩内容"
                sub_title = sub_title or "不容错过"

        logger.info(f"Titles: {main_title} / {sub_title}")

        # Add text overlays
        logger.info("Adding text overlays...")
        final_image = self.add_text_overlay(frame_path, main_title, sub_title)

        # Save final image
        if not filename:
            content_hash = hashlib.md5(f"{title}{main_title}".encode()).hexdigest()[:8]
            filename = f"thumbnail_{content_hash}.png"

        output_path = output_dir / filename
        with open(output_path, "wb") as f:
            f.write(final_image)

        logger.info(f"Generated thumbnail from frame: {output_path}")
        return output_path

    async def generate_for_timeline(
        self,
        title: str,
        subtitles: List[dict],
        video_path: Path,
        output_dir: Path,
        filename: Optional[str] = None,
        timestamp: Optional[float] = None,
        main_title: Optional[str] = None,
        sub_title: Optional[str] = None,
    ) -> Optional[Path]:
        """Generate a YouTube-style thumbnail for a timeline.

        Args:
            title: Video title
            subtitles: List of subtitle dicts with 'start', 'end', 'en' keys
            video_path: Path to source video
            output_dir: Directory to save thumbnail
            filename: Optional filename
            timestamp: Optional specific timestamp for frame extraction
            main_title: Optional pre-specified main title
            sub_title: Optional pre-specified sub title

        Returns:
            Path to generated thumbnail or None
        """
        if not self.enabled:
            logger.warning("Thumbnail generation disabled (no LLM API key)")
            return None

        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        # Step 1: Get timestamp (use provided or analyze for best moment)
        if timestamp is not None:
            logger.info(f"Using user-specified timestamp: {timestamp}s")
        else:
            logger.info("Analyzing emotional moments...")
            timestamp, reason = await self.analyze_emotional_moments(subtitles)

        # Step 2: Generate clickbait titles (if not provided)
        if not main_title or not sub_title:
            logger.info("Generating clickbait titles...")
            gen_main, gen_sub = await self.generate_clickbait_title(title, subtitles)
            main_title = main_title or gen_main
            sub_title = sub_title or gen_sub
        logger.info(f"Titles: {main_title} / {sub_title}")

        # Step 3: Extract frame from video
        logger.info(f"Extracting frame at {timestamp}s...")
        frame_path = output_dir / "temp_frame.jpg"
        frame_result = self.extract_frame(video_path, timestamp, frame_path)

        if not frame_result:
            # Fallback: try at 10 seconds
            logger.warning("Frame extraction failed, trying fallback at 10s...")
            frame_result = self.extract_frame(video_path, 10.0, frame_path)

        if not frame_result:
            logger.error("Failed to extract frame from video")
            return None

        # Step 4: Add text overlays
        logger.info("Adding text overlays...")
        final_image = self.add_text_overlay(frame_path, main_title, sub_title)

        # Clean up temp frame
        try:
            frame_path.unlink()
        except Exception:
            pass

        # Save final image
        if not filename:
            content_hash = hashlib.md5(f"{title}{main_title}{timestamp}".encode()).hexdigest()[:8]
            filename = f"thumbnail_{content_hash}.png"

        output_path = output_dir / filename
        with open(output_path, "wb") as f:
            f.write(final_image)

        logger.info(f"Generated thumbnail from video frame: {output_path}")
        return output_path
