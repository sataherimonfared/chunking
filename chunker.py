"""
Chunking logic for DESY crawled MD files.
Uses RegexChunking (heading-based) with optional Sliding Window fallback.
See PLAN.md for specification.
"""

import re
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

# Config
from . import config


def _approx_tokens(text: str) -> int:
    """Approximate token count: ~1.3 tokens per word."""
    return int(len(text.split()) * 1.3)


def _sliding_window_chunks(text: str, window_size: int, overlap: int) -> list[str]:
    """Split text into overlapping word windows."""
    words = text.split()
    if len(words) <= window_size:
        return [text] if words else []
    step = window_size - overlap
    chunks = []
    for i in range(0, len(words), step):
        chunk_words = words[i : i + window_size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
    return chunks


def _is_boilerplate(section_heading: str) -> bool:
    """Check if section heading matches boilerplate patterns."""
    h = section_heading.strip()
    for pat in config.BOILERPLATE_PATTERNS:
        if pat.lower() in h.lower():
            return True
    return False


def _normalize_heading_for_compare(heading: str) -> str:
    """Normalize section heading for comparison: strip markdown links [text](url) -> text."""
    s = heading.strip()
    s = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", s)
    s = re.sub(r"\s*:\s*", ": ", s)  # normalize "A:B" and "A: B" to "A: B"
    return " ".join(s.split()).lower()


def _dedupe_chunks_by_heading(chunks: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """
    Option B.2: If two consecutive chunks share the same section_heading and one is
    very short, merge the short one into the longer chunk.
    """
    if not chunks:
        return chunks

    deduped: list[tuple[str, dict]] = []
    for text, meta in chunks:
        if not deduped:
            deduped.append((text, meta))
            continue

        prev_text, prev_meta = deduped[-1]
        curr_heading = meta["section_heading"]
        prev_heading = prev_meta["section_heading"]
        curr_words = meta["word_count"]

        prev_norm = _normalize_heading_for_compare(prev_heading)
        curr_norm = _normalize_heading_for_compare(curr_heading)

        if (
            prev_norm
            and curr_norm
            and prev_norm == curr_norm
            and curr_words < config.DEDUPE_SHORT_THRESHOLD
        ):
            merged_text = prev_text.rstrip() + "\n\n" + text.strip()
            prev_meta["word_count"] = len(merged_text.split())
            deduped[-1] = (merged_text, prev_meta)
        else:
            deduped.append((text, meta))

    return deduped


def _extract_subdomain(url: str) -> str:
    """Extract subdomain/host from URL (e.g. desy.de, innovation.desy.de)."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or ""
        # Remove www. for consistency
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or ""
    except Exception:
        return ""


def extract_metadata(content: str) -> tuple[str, str | None, str | None, str]:
    """
    Extract source_url, page_title, page_subtitle, and body from MD content.

    Returns:
        (source_url, page_title, page_subtitle, body)
    """
    source_url = ""
    page_title = "Untitled"
    page_subtitle: str | None = None

    # Match "# Source URL" block and capture URL
    m = re.search(
        r"^\s*#\s+Source\s+URL\s*\n\s*\n\s*([^\n]+)",
        content,
        re.MULTILINE | re.I,
    )
    if m:
        source_url = m.group(1).strip()

    # Find # headings (not "Source URL") for title and subtitle
    h1_matches = re.findall(r"^\s*#\s+(.+)$", content, re.MULTILINE)
    h1_headings = [
        h.strip()
        for h in h1_matches
        if "source url" not in h.lower()
    ]
    if h1_headings:
        page_title = h1_headings[0]
        page_subtitle = h1_headings[1] if len(h1_headings) > 1 else None

    # Body: content after "# Source URL\n\n<url>\n\n" for chunking
    body = content
    m = re.search(
        r"^\s*#\s+Source\s+URL\s*\n\s*\n\s*[^\n]+\s*\n\s*\n",
        content,
        re.MULTILINE | re.I | re.DOTALL,
    )
    if m:
        body = content[m.end() :]

    return source_url, page_title, page_subtitle, body


def chunk_md_content(
    content: str,
    source_url: str,
    page_title: str,
    page_subtitle: str | None,
    file_path: str,
    depth: int,
) -> list[tuple[str, dict]]:
    """
    Chunk MD body and yield (chunk_text, metadata_dict) for each chunk.

    Returns list of (text, metadata) tuples.
    """
    subdomain = _extract_subdomain(source_url)

    # Split on ## headings
    parts = re.split(config.SPLIT_PATTERN, content, flags=re.MULTILINE)

    chunks: list[tuple[str, dict]] = []
    for idx, part in enumerate(parts):
        raw = part.strip()
        if not raw:
            continue

        # First part: intro (no ## before it) - section_heading is empty or page_title
        if idx == 0:
            section_heading = ""
            chunk_text = raw
        else:
            # First line of part is the section heading (rest was after ## )
            lines = raw.split("\n", 1)
            section_heading = lines[0].strip()
            chunk_text = lines[1].strip() if len(lines) > 1 else ""
            # Prepend heading for context
            chunk_text = f"## {section_heading}\n\n{chunk_text}" if chunk_text else f"## {section_heading}"

        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        word_count = len(chunk_text.split())
        if word_count < config.MIN_CHUNK_WORDS:
            continue

        # Fallback: sliding window if chunk exceeds token limit
        approx_tokens = _approx_tokens(chunk_text)
        if approx_tokens > config.TOKEN_LIMIT:
            sub_chunks = _sliding_window_chunks(
                chunk_text, config.WINDOW_SIZE, config.OVERLAP
            )
            for sub_idx, sub_text in enumerate(sub_chunks):
                meta = {
                    "source_url": source_url,
                    "page_title": page_title,
                    "page_subtitle": page_subtitle,
                    "section_heading": section_heading,
                    "chunk_index": len(chunks) + sub_idx,
                    "chunk_count": 0,  # Set later
                    "depth": depth,
                    "file_path": file_path,
                    "subdomain": subdomain,
                    "word_count": len(sub_text.split()),
                    "is_boilerplate": _is_boilerplate(section_heading),
                }
                chunks.append((sub_text, meta))
        else:
            meta = {
                "source_url": source_url,
                "page_title": page_title,
                "page_subtitle": page_subtitle,
                "section_heading": section_heading,
                "chunk_index": len(chunks),
                "chunk_count": 0,
                "depth": depth,
                "file_path": file_path,
                "subdomain": subdomain,
                "word_count": word_count,
                "is_boilerplate": _is_boilerplate(section_heading),
            }
            chunks.append((chunk_text, meta))

    # Option B.2: dedupe consecutive chunks with same section_heading when one is very short
    chunks = _dedupe_chunks_by_heading(chunks)

    # Update chunk_count for all
    n = len(chunks)
    for i, (text, meta) in enumerate(chunks):
        meta["chunk_count"] = n
        meta["chunk_index"] = i

    return chunks


def process_md_file(md_path: Path, depth: int, run_id: str) -> list[tuple[str, dict]]:
    """
    Read MD file, extract metadata, chunk, and return list of (text, metadata).
    """
    content = md_path.read_text(encoding="utf-8", errors="replace")
    source_url, page_title, page_subtitle, body = extract_metadata(content)

    # Relative path for metadata: depth_N/filename.md
    file_path = f"depth_{depth}/{md_path.name}"

    return chunk_md_content(
        content=body,
        source_url=source_url,
        page_title=page_title,
        page_subtitle=page_subtitle,
        file_path=file_path,
        depth=depth,
    )
