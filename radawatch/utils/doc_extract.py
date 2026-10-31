"""Document text extraction: DOCX, PDF, RTF (ported from omr-monitor and cpr-redaktor)."""

from __future__ import annotations

import re
from pathlib import Path


def docx_to_text(data: bytes) -> str:
    import io
    import zipfile
    import html as htmllib
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return re.sub(r"\n{3,}", "\n\n", htmllib.unescape(re.sub(r"<[^>]+>", "", xml))).strip()


def extract_text(path: str | Path) -> str | None:
    """Extract text from a document file. Returns None if format is unsupported."""
    p = Path(path)
    ext = p.suffix.lower()
    data = p.read_bytes()

    if ext == ".docx":
        return docx_to_text(data)
    if ext == ".txt":
        return data.decode("utf-8", "replace")
    if ext in (".htm", ".html"):
        from .text import strip_tags
        text = data.decode("utf-8", "replace")
        return strip_tags(re.sub(r"</p>|<br\s*/?>", "\n", text, flags=re.I))

    return None
