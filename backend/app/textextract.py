"""Best-effort text extraction from uploaded evidence, used for classification."""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

log = logging.getLogger(__name__)
MAX_CHARS = 20000
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".log", ".feature", ".html", ".htm", ".ini", ".cfg", ".properties"}


def extract_text(path: Path, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    try:
        if ext in TEXT_EXT:
            raw = path.read_bytes()[: MAX_CHARS * 4]
            text = raw.decode("utf-8", errors="replace")
            if ext in {".csv", ".tsv"}:
                rows = list(csv.reader(io.StringIO(text), delimiter="\t" if ext == ".tsv" else ","))[:60]
                text = "\n".join(" | ".join(r) for r in rows)
            return text[:MAX_CHARS]
        if ext == ".docx":
            import docx  # python-docx

            d = docx.Document(str(path))
            parts = [p.text for p in d.paragraphs if p.text.strip()]
            for t in d.tables[:10]:
                for row in t.rows[:40]:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
            return "\n".join(parts)[:MAX_CHARS]
        if ext in {".xlsx", ".xlsm"}:
            import openpyxl

            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            parts: list[str] = []
            for ws in wb.worksheets[:5]:
                parts.append(f"# Sheet: {ws.title}")
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i >= 60:
                        break
                    vals = [str(v) for v in row if v is not None]
                    if vals:
                        parts.append(" | ".join(vals))
            wb.close()
            return "\n".join(parts)[:MAX_CHARS]
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            parts = []
            for page in reader.pages[:15]:
                parts.append(page.extract_text() or "")
                if sum(len(p) for p in parts) > MAX_CHARS:
                    break
            return "\n".join(parts)[:MAX_CHARS]
        if ext == ".pptx":
            return ""  # filename-only classification; add python-pptx if needed
    except Exception as exc:  # corrupt or encrypted files should not block upload
        log.warning("Text extraction failed for %s: %s", filename, exc)
    return ""
