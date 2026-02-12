"""
Configuration for DESY chunking pipeline.
See PLAN.md for full specification.
"""

from pathlib import Path

# Paths (relative to project root, or absolute)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_BASE = PROJECT_ROOT / "desy_crawled"
OUTPUT_BASE = PROJECT_ROOT / "chunking" / "output"

# Run selection
RUN_ID = "2"  # Subfolder under desy_crawled (e.g. "1", "2")

# Chunking parameters
SPLIT_PATTERN = r"^\s*##\s+"  # Regex for primary split (## headings)
TOKEN_LIMIT = 512  # Max tokens per chunk before fallback (approx: words * 1.3)
WINDOW_SIZE = 400  # Words for sliding-window fallback
OVERLAP = 50  # Overlap for sliding-window fallback

# Boilerplate: section headings to mark as boilerplate (case-insensitive)
BOILERPLATE_PATTERNS = [
    "External Links",
    "Contact",
    "Career",
    "DESY Research",
    "DESY Research Centre",
    "DESY USER's area",
    "DESY calendar",
    "DESY for business",
    "DESY in Easy Language",
    "DESY latest news",
    "Zum Seitenanfang",
    "Back to top"
]

# Min words to keep a chunk (skip very short)
MIN_CHUNK_WORDS = 15

# Dedupe by section_heading (Option B.2): merge if consecutive chunks share heading and one is very short
DEDUPE_SHORT_THRESHOLD = 25  # words; chunk shorter than this gets merged into previous when headings match
