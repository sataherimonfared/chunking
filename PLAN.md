# Chunking Plan for DESY Crawled Content

**Target folder:** `chunking/`  
**Goal:** Produce chunks + metadata from crawled MD files using RegexChunking (heading-based) with metadata including page title and subtitle.

---

## 1. Input

- **Source:** `desy_crawled/<run_id>/depth_<N>/*.md`
- **Format:** Markdown files, one file per URL
- **Structure:** `# Source URL`, `# <Title>`, optional intro, then `##` / `###` sections

---

## 2. Chunking Strategy

### 2.1 Primary: RegexChunking (heading-based)

- **Split pattern:** `^\s*##\s+` (and optionally `^\s*###\s+`)
- **Logic:** Split on `##` boundaries; each resulting block = one chunk
- **Rationale:** DESY pages use consistent heading structure; sections align with topic boundaries

### 2.2 Fallback: Sliding Window on Oversized Chunks

- **Trigger:** When a chunk exceeds token limit (e.g. 512 tokens)
- **Action:** Apply Crawl4AI `SlidingWindowChunking` or `OverlappingWindowChunking` on that chunk only
- **Params:** e.g. `window_size=400`, `overlap=50` words (tune as needed)

### 2.3 Boilerplate Handling

- **Detection:** Chunk whose section_heading matches `External Links` or similar boilerplate patterns
- **Metadata:** Set `is_boilerplate: true` so retrieval can filter/down-rank

---

## 3. Metadata Schema (per chunk)

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `source_url` | str | From `# Source URL` in MD | Required for attribution |
| `page_title` | str | First `#` heading (after Source URL) | Main page title |
| `page_subtitle` | str \| null | Second `#` or first `##` if used as subtitle | Optional |
| `section_heading` | str | The `##` or `###` that heads this chunk | e.g. "PETRA III", "External Links" |
| `chunk_index` | int | 0-based index among all chunks of the page | 0, 1, 2, … |
| `chunk_count` | int | Total chunks for this page | For "chunk 3 of 12" |
| `depth` | int | From folder `depth_N` | 0, 1, 2, … |
| `file_path` | str | Relative path to MD file | e.g. `depth_1/desy.de_desy_research_accelerators_index_eng.html.md` |
| `subdomain` | str | Parsed from source_url | e.g. desy.de, innovation.desy.de, petra4.desy.de |
| `word_count` | int | Word count of chunk text | Optional |
| `is_boilerplate` | bool | True if matches boilerplate patterns | Default false |

---

## 4. Title and Subtitle Extraction

- **Page title:** First `# ` heading after `# Source URL` (e.g. `# Accelerators` → `"Accelerators"`)
- **Page subtitle:** Second `# ` heading if present, or first `## ` heading when it acts as subtitle (short, at top); else `null`
- **Section heading:** The `##` or `###` that introduces the current chunk; empty string for intro block (before first `##`)

---

## 5. Output Format

### 5.1 Per-file output (JSON Lines)

**Path:** `chunking/output/<run_id>/depth_<N>/<filename>.jsonl`

Each line = one JSON object:

```json
{
  "text": "<chunk text>",
  "metadata": {
    "source_url": "https://desy.de/...",
    "page_title": "Accelerators",
    "page_subtitle": "Scientific information about the Accelerator Division",
    "section_heading": "PETRA III",
    "chunk_index": 5,
    "chunk_count": 12,
    "depth": 1,
    "file_path": "depth_1/desy.de_desy_research_accelerators_index_eng.html.md",
    "subdomain": "desy.de",
    "word_count": 42,
    "is_boilerplate": false
  }
}
```

### 5.2 Aggregated index (optional)

**Path:** `chunking/output/<run_id>/chunks_index.json`

Summary of all chunks: list of `{ file_path, chunk_count, source_url }` for quick inspection.

---

## 6. Processing Pipeline

```
1. List all MD files under desy_crawled/<run_id>/depth_*/
2. For each MD file:
   a. Read file content
   b. Extract source_url (first line after "# Source URL")
   c. Extract page_title (first # heading)
   d. Extract page_subtitle (second # or first ##, if applicable)
   e. Split on ## (and optionally ###) via RegexChunking
   f. For each chunk:
      - Detect section_heading (the ##/### that introduced it)
      - Check is_boilerplate (e.g. "External Links")
      - If chunk exceeds token limit → apply SlidingWindow fallback
      - Build metadata object
      - Append to JSONL output
3. Write chunks to chunking/output/<run_id>/depth_<N>/<basename>.jsonl
4. (Optional) Write chunks_index.json
```

---

## 7. Config / Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INPUT_BASE` | `desy_crawled/` | Root of crawled output |
| `OUTPUT_BASE` | `chunking/output/` | Root of chunking output |
| `RUN_ID` | `2` or configurable | Subfolder under desy_crawled |
| `SPLIT_PATTERN` | `^\s*##\s+` | Regex for primary split |
| `TOKEN_LIMIT` | 512 | Max tokens per chunk before fallback |
| `WINDOW_SIZE` | 400 | Words for sliding-window fallback |
| `OVERLAP` | 50 | Overlap for sliding-window fallback |
| `BOILERPLATE_PATTERNS` | `["External Links", "Contact", …]` | Headings to mark as boilerplate |

---

## 8. File Layout in `chunking/`

```
chunking/
├── PLAN.md                    # This plan
├── config.py                  # Configurable parameters
├── chunker.py                 # Chunking logic + metadata
├── run_chunking.py            # CLI / main entry point
├── output/                    # Output root
│   └── <run_id>/
│       ├── depth_0/
│       │   ├── desy.de_index_eng.html.md.jsonl
│       │   └── ...
│       ├── depth_1/
│       │   └── ...
│       ├── depth_2/
│       │   └── ...
│       └── chunks_index.json  # Optional
└── README.md                 # How to run
```

---

## 9. Edge Cases

- **No `##` in file:** Treat entire body (after title) as one chunk
- **Empty chunks:** Skip or filter (whitespace-only)
- **Very short chunks (< N words):** Optionally merge with next chunk or mark as boilerplate if link-only
- **Multiple runs:** Use `RUN_ID` or timestamp to avoid overwriting

---

## 10. Dependencies

- Same env as crawler: crawl4ai, beautifulsoup4 (if needed for HTML fallback)
- Optional: tiktoken for token counting
- Stdlib: re, json, pathlib
