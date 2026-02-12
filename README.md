# DESY Chunking Pipeline

Chunks crawled DESY markdown files into smaller units with metadata, ready for embedding and FAISS indexing.

See `PLAN.md` for the full specification.

---

## What it does

- Reads MD files from `desy_crawled/<run_id>/depth_*/`
- Splits on `##` headings (RegexChunking)
- Applies sliding-window fallback for oversized chunks
- Outputs JSONL files with `text` + `metadata` (source_url, page_title, section_heading, etc.)

---

## Requirements

Same environment as the crawler (see project `requirements.txt`). No extra dependencies.

---

## How to run

**From the chunking directory:**

```bash
cd /home/taheri/crawl4ai/chunking
python run_chunking.py --run-id 2 --write-index
```

**From the project root:**

```bash
cd /path/to/crawl4ai
python -m chunking.run_chunking --run-id 2 --write-index
```

| Option | Default | Description |
|--------|---------|-------------|
| `--run-id` | `2` | Subfolder under `desy_crawled` to process |
| `--write-index` | off | Write `chunks_index.json` summary |
| `--input` | `desy_crawled` | Override input base path |
| `--output` | `chunking/output` | Override output base path |

---

## Output layout

```
chunking/output/
└── <run_id>/
    ├── depth_0/
    │   ├── desy.de_index_eng.html.md.jsonl
    │   └── ...
    ├── depth_1/
    │   └── ...
    ├── depth_2/
    │   └── ...
    └── chunks_index.json   # if --write-index
```

Each `.jsonl` file has one JSON object per line:

```json
{"text": "<chunk content>", "metadata": {"source_url": "...", "page_title": "...", "section_heading": "...", ...}}
```

---

## Configuration

Edit `config.py` to change:

- `RUN_ID` — default run to process
- `SPLIT_PATTERN` — regex for splitting (default: `##` headings)
- `TOKEN_LIMIT`, `WINDOW_SIZE`, `OVERLAP` — sliding-window fallback
- `BOILERPLATE_PATTERNS` — headings marked as `is_boilerplate: true`
