"""
论文翻译服务
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Mapping, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import hashlib
from openai import OpenAI
import httpx

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import LLM_FILTER_CONFIG
from services.prompt_service import get_prompt, get_rendered_prompt

logger = logging.getLogger(__name__)


class TranslationService:
    """论文翻译服务类"""

    _chunk_cache: Dict[str, str] = {}
    _chunk_cache_lock = threading.Lock()

    def __init__(self, config: Optional[Mapping[str, object]] = None):
        self.config: Mapping[str, object] = config or LLM_FILTER_CONFIG

        api_key_raw = self.config.get("api_key")
        base_url_raw = self.config.get("base_url")
        api_key = api_key_raw if isinstance(api_key_raw, str) else None
        base_url = base_url_raw if isinstance(base_url_raw, str) else None

        # 与精读对话链路保持一致：禁用环境代理，避免系统代理导致连接抖动
        http_client = httpx.Client(
            timeout=120.0,
            follow_redirects=True,
            proxy=None,
            trust_env=False,
        )

        if api_key and base_url:
            self.client = OpenAI(
                api_key=api_key, base_url=base_url, http_client=http_client
            )
        elif api_key:
            self.client = OpenAI(api_key=api_key, http_client=http_client)
        elif base_url:
            self.client = OpenAI(base_url=base_url, http_client=http_client)
        else:
            self.client = OpenAI(http_client=http_client)

        model_raw = self.config.get("model", "gpt-3.5-turbo")
        self.model = model_raw if isinstance(model_raw, str) else "gpt-3.5-turbo"

        temperature_raw = self.config.get("translation_temperature", 0.3)
        self.temperature = (
            float(temperature_raw) if isinstance(temperature_raw, (int, float)) else 0.3
        )

        max_tokens_raw = self.config.get("translation_max_tokens", 4096)
        self.max_tokens = (
            int(max_tokens_raw) if isinstance(max_tokens_raw, (int, float)) else 4096
        )

        self._last_alignment: Dict[str, List[str]] = {
            "source_blocks": [],
            "translated_blocks": [],
        }

        logger.info("TranslationService初始化完成")

    def translate_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """翻译论文标题和摘要"""
        try:
            title = paper["Title"]
            abstract = paper["Abstract"]

            variables = {"title": title, "abstract": abstract}
            prompt = get_rendered_prompt("translation_template", variables)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": get_prompt("translation_system_prompt"),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content
            result = self._parse_translation(content or "")

            paper["TitleCN"] = result["TitleCN"]
            paper["AbstractCN"] = result["AbstractCN"]

            logger.debug(f"翻译完成: {result['TitleCN'][:30]}...")

            return paper

        except Exception as e:
            logger.error(f"翻译论文时出错: {str(e)}")
            paper["TitleCN"] = paper["Title"]
            paper["AbstractCN"] = paper["Abstract"]
            return paper

    def translate_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量翻译论文"""
        if not papers:
            return []

        logger.info(f"开始翻译，共 {len(papers)} 篇论文")

        translated_papers = []
        for idx, paper in enumerate(papers, 1):
            logger.info(f"  [{idx}/{len(papers)}] 翻译: {paper['Title'][:50]}...")
            translated_paper = self.translate_paper(paper)
            translated_papers.append(translated_paper)

        logger.info("翻译完成")
        return translated_papers

    def _parse_translation(self, response_text: str) -> Dict[str, str]:
        """解析翻译响应"""
        try:
            response_text = response_text.strip()

            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            result = json.loads(response_text)

            return {
                "TitleCN": result.get("TitleCN", result.get("title_zh", "")).strip(),
                "AbstractCN": result.get(
                    "AbstractCN", result.get("abstract_zh", "")
                ).strip(),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return self._extract_translation_from_text(response_text)
        except Exception as e:
            logger.error(f"解析翻译响应时出错: {e}")
            return {"TitleCN": "", "AbstractCN": ""}

    def _extract_translation_from_text(self, text: str) -> Dict[str, str]:
        """从文本中提取翻译"""
        title_cn = ""
        abstract_cn = ""

        title_match = re.search(
            r'["\']?(?:TitleCN|title_zh)["\']?\s*[:：]\s*["\']([^"\']+)["\']',
            text,
            re.DOTALL,
        )
        if title_match:
            title_cn = title_match.group(1).strip()

        abstract_match = re.search(
            r'["\']?(?:AbstractCN|abstract_zh)["\']?\s*[:：]\s*["\']([^"\']+)["\']',
            text,
            re.DOTALL,
        )
        if abstract_match:
            abstract_cn = abstract_match.group(1).strip()

        return {"TitleCN": title_cn, "AbstractCN": abstract_cn}

    def translate_text(
        self,
        text: str,
        from_lang: str = "en",
        to_lang: str = "zh",
        cache_scope: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """通用文本翻译（支持长文档自动分块）"""
        if not text or not text.strip():
            return ""

        self._last_alignment = {"source_blocks": [], "translated_blocks": []}

        chunk_size = 4000
        chunks = self._build_markdown_chunks(text, chunk_size)
        total_chunks = len(chunks)
        if progress_callback:
            progress_callback(
                {
                    "status": "processing",
                    "current": 0,
                    "total": total_chunks,
                    "progress": 0,
                    "message": "开始翻译...",
                }
            )

        if len(chunks) == 1:
            result = self._translate_chunk(chunks[0], from_lang, to_lang, cache_scope)
            if progress_callback:
                progress_callback(
                    {
                        "status": "processing",
                        "current": 1,
                        "total": total_chunks,
                        "progress": 100,
                        "message": "翻译完成",
                    }
                )
            return result

        max_workers_raw = self.config.get("max_workers", 16)
        max_workers = (
            int(max_workers_raw)
            if isinstance(max_workers_raw, (int, float))
            else 16
        )
        max_workers = max(1, min(max_workers, total_chunks))

        logger.info(f"开始并行全文翻译，共 {total_chunks} 个分块，使用 {max_workers} 个线程")

        translated_parts: List[str] = [""] * total_chunks
        completed_count = 0
        pending_items: List[tuple[int, str]] = []
        source_blocks_all: List[str] = []
        translated_blocks_all: List[str] = []

        # 先命中分块缓存，避免重复翻译
        for idx, chunk in enumerate(chunks, 1):
            cached = self._get_cached_chunk_translation(
                chunk,
                from_lang,
                to_lang,
                cache_scope,
            )
            if cached is not None:
                translated_parts[idx - 1] = cached
                cached_source_blocks = self._split_markdown_blocks(chunk) or [chunk]
                cached_translated_blocks = self._split_markdown_blocks(cached) or [cached]
                source_blocks_all.extend(cached_source_blocks)
                translated_blocks_all.extend(cached_translated_blocks)
                completed_count += 1
                chunk_summary = self._summarize_chunk(chunk)
                if progress_callback:
                    progress_callback(
                        {
                            "status": "processing",
                            "current": completed_count,
                            "total": total_chunks,
                            "progress": int((completed_count / total_chunks) * 100),
                            "message": f"复用已翻译分块 {idx}/{total_chunks}：{chunk_summary}",
                        }
                    )
            else:
                pending_items.append((idx, chunk))

        if not pending_items:
            return "\n\n".join(translated_parts)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(
                    self._translate_chunk_with_alignment,
                    chunk,
                    from_lang,
                    to_lang,
                    cache_scope,
                ): idx
                for idx, chunk in pending_items
            }

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                chunk = chunks[idx - 1]
                logger.info(f"  翻译分块 [{idx}/{total_chunks}] ({len(chunk)} 字符)")

                try:
                    result, source_blocks, translated_blocks = future.result()
                except Exception as e:
                    logger.error(f"分块 {idx} 翻译任务异常: {e}")
                    result = chunk
                    source_blocks = self._split_markdown_blocks(chunk) or [chunk]
                    translated_blocks = source_blocks

                translated_parts[idx - 1] = result
                source_blocks_all.extend(source_blocks)
                translated_blocks_all.extend(translated_blocks)
                completed_count += 1

                chunk_summary = self._summarize_chunk(chunk)
                if progress_callback:
                    progress_callback(
                        {
                            "status": "processing",
                            "current": completed_count,
                            "total": total_chunks,
                            "progress": int((completed_count / total_chunks) * 100),
                            "message": f"正在翻译分块 {idx}/{total_chunks}：{chunk_summary}",
                        }
                    )

        self._last_alignment = {
            "source_blocks": source_blocks_all,
            "translated_blocks": translated_blocks_all,
        }
        return "\n\n".join(translated_parts)

    def get_last_alignment(self) -> Dict[str, List[str]]:
        """获取最近一次全文翻译的对齐分段。"""
        return {
            "source_blocks": list(self._last_alignment.get("source_blocks", [])),
            "translated_blocks": list(self._last_alignment.get("translated_blocks", [])),
        }

    def _build_markdown_chunks(self, text: str, max_chars: int) -> List[str]:
        """按 Markdown 结构优先切分，尽量保留完整小节。"""
        normalized_text = text.replace("\r\n", "\n").strip()
        if len(normalized_text) <= max_chars:
            return [normalized_text]

        sections = self._split_markdown_sections(normalized_text)
        chunks: List[str] = []
        current_section: List[str] = []
        current_length = 0

        for section in sections:
            section_length = len(section)
            if section_length > max_chars:
                if current_section:
                    chunks.append("\n\n".join(current_section).strip())
                    current_section = []
                    current_length = 0

                chunks.extend(self._split_large_markdown_section(section, max_chars))
                continue

            if current_section and current_length + section_length > max_chars:
                chunks.append("\n\n".join(current_section).strip())
                current_section = [section]
                current_length = section_length
            else:
                current_section.append(section)
                current_length += section_length

        if current_section:
            chunks.append("\n\n".join(current_section).strip())

        return [chunk for chunk in chunks if chunk]

    def _split_markdown_sections(self, text: str) -> List[str]:
        """按标题将 Markdown 切成若干小节。"""
        blocks = self._split_markdown_blocks(text)
        if not blocks:
            return [text]

        sections: List[str] = []
        current_blocks: List[str] = []

        for block in blocks:
            if self._is_markdown_heading(block) and current_blocks:
                sections.append("\n\n".join(current_blocks).strip())
                current_blocks = [block]
            else:
                current_blocks.append(block)

        if current_blocks:
            sections.append("\n\n".join(current_blocks).strip())

        return [section for section in sections if section]

    def _split_large_markdown_section(self, section: str, max_chars: int) -> List[str]:
        """将过长小节继续按段落块拆分。"""
        blocks = self._split_markdown_blocks(section)
        if not blocks:
            return [section]

        heading = blocks[0] if self._is_markdown_heading(blocks[0]) else ""
        body_blocks = blocks[1:] if heading else blocks
        chunks: List[str] = []
        current_blocks: List[str] = [heading] if heading else []
        current_length = len(heading) if heading else 0

        for block in body_blocks:
            block_length = len(block)
            if current_blocks and current_length + block_length > max_chars:
                chunks.append("\n\n".join(current_blocks).strip())
                current_blocks = [heading] if heading else []
                current_length = len(heading) if heading else 0

            if not current_blocks and block_length > max_chars:
                chunks.extend(self._split_oversized_block(block, max_chars))
                continue

            current_blocks.append(block)
            current_length += block_length

        if current_blocks:
            chunks.append("\n\n".join(current_blocks).strip())

        return [chunk for chunk in chunks if chunk]

    def _split_oversized_block(self, block: str, max_chars: int) -> List[str]:
        """将单个超长块按行和句子继续拆分。"""
        stripped_block = block.strip()
        if not stripped_block:
            return []

        if stripped_block.startswith("```"):
            return [stripped_block]

        lines = [line for line in stripped_block.split("\n") if line.strip()]
        if not lines:
            return [stripped_block]

        chunks: List[str] = []
        current_lines: List[str] = []
        current_length = 0

        for line in lines:
            line_length = len(line)
            if current_lines and current_length + line_length > max_chars:
                chunks.append("\n".join(current_lines).strip())
                current_lines = []
                current_length = 0

            if line_length > max_chars:
                sentence_chunks = self._split_long_line(line, max_chars)
                if current_lines:
                    chunks.append("\n".join(current_lines).strip())
                    current_lines = []
                    current_length = 0
                chunks.extend(sentence_chunks)
                continue

            current_lines.append(line)
            current_length += line_length

        if current_lines:
            chunks.append("\n".join(current_lines).strip())

        return [chunk for chunk in chunks if chunk]

    def _split_long_line(self, line: str, max_chars: int) -> List[str]:
        """将超长单行按句子切分。"""
        sentence_parts = re.split(r'(?<=[。！？!?\.])\s+', line)
        if len(sentence_parts) == 1:
            return [line]

        chunks: List[str] = []
        current_parts: List[str] = []
        current_length = 0

        for part in sentence_parts:
            part = part.strip()
            if not part:
                continue

            part_length = len(part)
            if current_parts and current_length + part_length > max_chars:
                chunks.append(" ".join(current_parts).strip())
                current_parts = []
                current_length = 0

            if part_length > max_chars:
                chunks.append(part)
                continue

            current_parts.append(part)
            current_length += part_length

        if current_parts:
            chunks.append(" ".join(current_parts).strip())

        return [chunk for chunk in chunks if chunk]

    def _split_markdown_blocks(self, text: str) -> List[str]:
        """按 Markdown 块切分，保留代码块整体。"""
        lines = text.split("\n")
        blocks: List[str] = []
        current_lines: List[str] = []
        in_code_block = False

        for line in lines:
            stripped_line = line.strip()

            if stripped_line.startswith("```"):
                if current_lines and not in_code_block:
                    blocks.extend(self._flush_paragraph_block(current_lines))
                    current_lines = []

                current_lines.append(line)
                in_code_block = not in_code_block

                if not in_code_block:
                    blocks.append("\n".join(current_lines).strip())
                    current_lines = []
                continue

            if in_code_block:
                current_lines.append(line)
                continue

            if not stripped_line:
                if current_lines:
                    blocks.extend(self._flush_paragraph_block(current_lines))
                    current_lines = []
                continue

            if self._is_markdown_heading_line(stripped_line):
                if current_lines:
                    blocks.extend(self._flush_paragraph_block(current_lines))
                    current_lines = []
                blocks.append(stripped_line)
                continue

            current_lines.append(line)

        if current_lines:
            if in_code_block:
                blocks.append("\n".join(current_lines).strip())
            else:
                blocks.extend(self._flush_paragraph_block(current_lines))

        return [block for block in blocks if block]

    def _flush_paragraph_block(self, lines: List[str]) -> List[str]:
        """把普通文本行合并成段落块。"""
        text = "\n".join(lines).strip()
        if not text:
            return []

        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
        return paragraphs or [text]

    def _is_markdown_heading_line(self, line: str) -> bool:
        """判断一行是否为 Markdown 标题。"""
        return bool(re.match(r"^#{1,6}\s+\S", line))

    def _is_markdown_heading(self, block: str) -> bool:
        """判断块是否为 Markdown 标题行。"""
        first_line = block.strip().split("\n", 1)[0].strip()
        return self._is_markdown_heading_line(first_line)

    def _summarize_chunk(self, chunk: str, max_len: int = 40) -> str:
        """提取分块摘要，优先显示小节标题。"""
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        if not lines:
            return "内容片段"

        heading = ""
        for line in lines:
            if self._is_markdown_heading_line(line):
                heading = re.sub(r"^#{1,6}\s+", "", line).strip()
                if heading:
                    break

        summary = heading or lines[0]
        summary = re.sub(r"\s+", " ", summary)
        if len(summary) > max_len:
            summary = summary[:max_len].rstrip() + "..."
        return summary

    def _build_alignment_markers(self, count: int) -> List[str]:
        """为分块内段落生成稳定标记。"""
        return [f"[[[DSBLOCK_{idx:04d}]]]" for idx in range(1, count + 1)]

    def _build_tagged_chunk_text(self, blocks: List[str], markers: List[str]) -> str:
        """将原始块包装为带标记文本，约束模型保留分段。"""
        tagged_parts: List[str] = []
        for marker, block in zip(markers, blocks):
            tagged_parts.append(f"{marker}\n{block}")
        return "\n\n".join(tagged_parts)

    def _parse_tagged_translation(
        self,
        translated_text: str,
        markers: List[str],
    ) -> Optional[List[str]]:
        """按标记回收翻译段落，保证段落一一对应。"""
        captured: List[str] = []
        for idx, marker in enumerate(markers):
            start = translated_text.find(marker)
            if start < 0:
                return None

            content_start = start + len(marker)
            next_start = -1
            if idx < len(markers) - 1:
                next_start = translated_text.find(markers[idx + 1], content_start)
                if next_start < 0:
                    return None

            content = (
                translated_text[content_start:next_start]
                if next_start >= 0
                else translated_text[content_start:]
            )
            captured.append(content.strip())

        return captured if len(captured) == len(markers) else None

    def _build_chunk_cache_key(self, text: str, from_lang: str, to_lang: str) -> str:
        model = self.model or ""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{from_lang}|{to_lang}|{model}|{digest}"

    def _extract_chunk_hash(self, cache_key: str) -> str:
        parts = cache_key.split("|")
        return parts[-1] if parts else cache_key

    def _get_persistent_chunk_translation(self, doi: str, cache_key: str) -> Optional[str]:
        try:
            from services.mysql_service import execute_query

            rows = execute_query(
                "SELECT translated_text FROM translation_chunk_cache WHERE doi = %s AND cache_key = %s LIMIT 1",
                (doi, cache_key),
            )
            if rows:
                return rows[0].get("translated_text")
        except Exception as e:
            logger.debug(f"读取持久化翻译缓存失败: {e}")
        return None

    def _set_persistent_chunk_translation(
        self,
        doi: str,
        cache_key: str,
        from_lang: str,
        to_lang: str,
        translated: str,
    ) -> None:
        try:
            from services.mysql_service import execute_update

            model = self.model or ""
            chunk_hash = self._extract_chunk_hash(cache_key)
            execute_update(
                """
                INSERT INTO translation_chunk_cache
                (doi, cache_key, source_lang, target_lang, model, chunk_hash, translated_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (doi, cache_key, from_lang, to_lang, model, chunk_hash, translated),
            )
        except Exception:
            try:
                from services.mysql_service import execute_update

                execute_update(
                    """
                    UPDATE translation_chunk_cache
                    SET translated_text = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE doi = %s AND cache_key = %s
                    """,
                    (translated, doi, cache_key),
                )
            except Exception as e:
                logger.debug(f"写入持久化翻译缓存失败: {e}")

    @classmethod
    def clear_chunk_cache_for_doi(cls, doi: str) -> int:
        """清除指定论文的持久化与内存分块缓存。"""
        deleted_rows = 0
        try:
            from services.mysql_service import execute_query, execute_update

            rows = execute_query(
                "SELECT cache_key FROM translation_chunk_cache WHERE doi = %s",
                (doi,),
            )
            cache_keys = [row.get("cache_key") for row in rows if row.get("cache_key")]

            if cache_keys:
                with cls._chunk_cache_lock:
                    for key in cache_keys:
                        cls._chunk_cache.pop(key, None)

            deleted_rows = execute_update(
                "DELETE FROM translation_chunk_cache WHERE doi = %s",
                (doi,),
            )
        except Exception as e:
            logger.warning(f"清除论文分块缓存失败 ({doi}): {e}")
        return deleted_rows

    def _get_cached_chunk_translation(
        self,
        text: str,
        from_lang: str,
        to_lang: str,
        cache_scope: Optional[str] = None,
    ) -> Optional[str]:
        cache_key = self._build_chunk_cache_key(text, from_lang, to_lang)
        with self._chunk_cache_lock:
            memory_hit = self._chunk_cache.get(cache_key)
        if memory_hit is not None:
            return memory_hit

        if cache_scope:
            persistent_hit = self._get_persistent_chunk_translation(cache_scope, cache_key)
            if persistent_hit is not None:
                with self._chunk_cache_lock:
                    self._chunk_cache[cache_key] = persistent_hit
                return persistent_hit
        return None

    def _set_cached_chunk_translation(
        self,
        text: str,
        from_lang: str,
        to_lang: str,
        translated: str,
        cache_scope: Optional[str] = None,
    ) -> None:
        if not translated:
            return
        cache_key = self._build_chunk_cache_key(text, from_lang, to_lang)
        with self._chunk_cache_lock:
            self._chunk_cache[cache_key] = translated
        if cache_scope:
            self._set_persistent_chunk_translation(
                cache_scope,
                cache_key,
                from_lang,
                to_lang,
                translated,
            )

    def _translate_chunk(
        self,
        text: str,
        from_lang: str,
        to_lang: str,
        cache_scope: Optional[str] = None,
    ) -> str:
        translated, _, _ = self._translate_chunk_with_alignment(
            text,
            from_lang,
            to_lang,
            cache_scope,
        )
        return translated

    def _translate_chunk_with_alignment(
        self,
        text: str,
        from_lang: str,
        to_lang: str,
        cache_scope: Optional[str] = None,
    ) -> tuple[str, List[str], List[str]]:
        """翻译单个文本块"""
        cached = self._get_cached_chunk_translation(
            text,
            from_lang,
            to_lang,
            cache_scope,
        )
        if cached is not None:
            source_blocks = self._split_markdown_blocks(text) or [text]
            translated_blocks = self._split_markdown_blocks(cached) or [cached]
            return cached, source_blocks, translated_blocks

        lang_names = {
            "en": "English", "zh": "Chinese", "ja": "Japanese",
            "ko": "Korean", "fr": "French", "de": "German",
        }
        src = lang_names.get(from_lang, from_lang)
        dst = lang_names.get(to_lang, to_lang)

        max_retries = 3
        base_retry_delay = 2
        blocks = self._split_markdown_blocks(text)
        if not blocks:
            blocks = [text]

        markers = self._build_alignment_markers(len(blocks))
        tagged_text = self._build_tagged_chunk_text(blocks, markers)

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a professional academic translator. Translate the following text from {src} to {dst}. Preserve Markdown structure, headings, lists, tables, formulas, citations, and code blocks exactly. Keep paragraph boundaries. IMPORTANT: marker lines like [[[DSBLOCK_0001]]] are structural anchors. Do NOT translate, remove, reorder, or modify any marker. Output all markers in original order, each followed by translated content.",
                        },
                        {"role": "user", "content": tagged_text},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                content = response.choices[0].message.content
                translated_raw = (content or "").strip()

                aligned_blocks = self._parse_tagged_translation(translated_raw, markers)
                if aligned_blocks is not None:
                    translated = "\n\n".join(aligned_blocks)
                else:
                    # 兜底：模型未完整保留标记时仍返回原结果，避免任务失败
                    translated = translated_raw
                    aligned_blocks = self._split_markdown_blocks(translated_raw) or [translated_raw]

                self._set_cached_chunk_translation(
                    text,
                    from_lang,
                    to_lang,
                    translated,
                    cache_scope,
                )
                return translated, blocks, aligned_blocks

            except Exception as e:
                if attempt < max_retries - 1:
                    retry_delay = base_retry_delay * (attempt + 1)
                    logger.warning(
                        f"翻译文本块失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {e}"
                    )
                    import time

                    time.sleep(retry_delay)
                else:
                    logger.error(f"翻译文本块失败: {e}")
                    fallback_blocks = self._split_markdown_blocks(text) or [text]
                    return text, fallback_blocks, fallback_blocks

        fallback_blocks = self._split_markdown_blocks(text) or [text]
        return text, fallback_blocks, fallback_blocks


def translate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """翻译论文的便捷函数"""
    service = TranslationService()
    return service.translate_papers(papers)
