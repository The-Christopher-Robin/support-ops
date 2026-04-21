"""Load knowledge-base docs from disk and chunk them for indexing.

Factored out of the scripts/ folder so the FastAPI app can re-use it to
auto-seed the in-memory store in mock mode.
"""

from __future__ import annotations

from pathlib import Path

from ..models import KBDocument


REPO_ROOT = Path(__file__).resolve().parents[2]
KB_ROOT = REPO_ROOT / "knowledge_base"
CATEGORIES = ("billing", "payroll", "onboarding", "vendor")


def chunk(text: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 > max_chars and buf:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf.strip())
    return chunks


def load_kb(root: Path | None = None) -> list[KBDocument]:
    root = root or KB_ROOT
    docs: list[KBDocument] = []
    for cat in CATEGORIES:
        for path in sorted((root / cat).glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            title = raw.splitlines()[0].lstrip("# ").strip() if raw else path.stem
            rel = str(path.relative_to(root)).replace("\\", "/")
            for i, piece in enumerate(chunk(raw)):
                docs.append(
                    KBDocument(
                        source_path=rel if i == 0 else f"{rel}#chunk-{i}",
                        title=title,
                        category=cat,  # type: ignore[arg-type]
                        content=piece,
                    )
                )
    return docs
