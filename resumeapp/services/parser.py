"""
Text extraction for uploaded resumes (PDF and DOCX).

extract_pdf_text() / extract_docx_text() keep their original names and still
return a plain string, so existing imports keep working.  New code should use
extract_with_meta(), which also reports layout details (tables, text boxes,
possible columns) and whether the file is unreadable (for example a scanned
PDF that needs OCR).

Fixes compared with the previous version:
* DOCX paragraphs are now separated by line breaks (they used to be glued
  together), and table, header and text-box text is included.
* PDF pages are separated by a line break.
* Damaged files raise ExtractionError with a readable message instead of a
  server error.
"""
import os

import pdfplumber
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

MIN_TEXT_CHARS = 200   # fewer readable characters than this = not a usable resume

PROBLEM_MESSAGES = {
    "scanned": (
        "This PDF looks like a scanned image: no selectable text was found. "
        "Resume AI cannot read scanned documents yet (OCR would be required). "
        "Please export your resume as a text-based PDF, or upload the DOCX version."
    ),
    "too_short": (
        "Only a very small amount of text could be read from this file, which is "
        "not enough to analyse a resume. Please check that you uploaded the right "
        "file and that it is not mostly images."
    ),
}


class ExtractionError(Exception):
    """Raised with a user-friendly message when a file cannot be read."""


def extract_pdf_text(path):
    return extract_with_meta(path)[0]


def extract_docx_text(path):
    return extract_with_meta(path)[0]


def extract_with_meta(path):
    """Return (text, meta). Raises ExtractionError for unreadable files."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        text, meta = _read_pdf(path)
    elif ext == ".docx":
        text, meta = _read_docx(path)
    else:
        raise ExtractionError("Only PDF (.pdf) and Word (.docx) files are supported.")

    meta["file_type"] = ext.lstrip(".")
    meta["chars"] = len(text.strip())
    meta["problem"] = _detect_problem(meta)
    return text, meta


def _detect_problem(meta):
    if meta["chars"] >= MIN_TEXT_CHARS:
        return None
    if meta["file_type"] == "pdf" and meta.get("images", 0) > 0:
        return "scanned"
    return "too_short"


# ----------------------------------------------------------------- PDF

def _read_pdf(path):
    pages, tables, images, multi = [], 0, 0, False
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
                images += len(page.images)
                try:
                    tables += len(page.find_tables())
                except Exception:
                    pass
                if not multi and _looks_multicolumn(page):
                    multi = True
    except Exception as exc:
        raise ExtractionError(
            "This PDF could not be opened. It may be damaged or password-protected."
        ) from exc

    meta = {
        "pages": page_count,
        "tables": tables,
        "images": images,
        "text_boxes": 0,
        "multi_column": multi,
    }
    return "\n".join(pages), meta


def _looks_multicolumn(page):
    """
    Heuristic: many lines contain a wide gap, and the text after that gap starts
    at nearly the same x position on most of them (a second column). Right-aligned
    dates do not trigger it because their start positions vary.
    """
    try:
        words = page.extract_words()
    except Exception:
        return False
    if len(words) < 60:
        return False

    width = float(page.width)
    rows = {}
    for w in words:
        rows.setdefault(round(w["top"] / 4), []).append(w)

    starts, wide_rows = [], 0
    for ws in rows.values():
        if len(ws) < 4:
            continue
        wide_rows += 1
        ws.sort(key=lambda w: w["x0"])
        best_gap, best_idx = 0, -1
        for i in range(len(ws) - 1):
            gap = ws[i + 1]["x0"] - ws[i]["x1"]
            if gap > best_gap:
                best_gap, best_idx = gap, i
        if best_gap > width * 0.06 and best_idx >= 1 and len(ws) - best_idx - 1 >= 2:
            starts.append(ws[best_idx + 1]["x0"])

    if wide_rows < 8 or len(starts) < 6 or len(starts) < 0.4 * wide_rows:
        return False

    starts.sort()
    window, best, j = width * 0.025, 0, 0
    for i in range(len(starts)):
        while starts[i] - starts[j] > window:
            j += 1
        best = max(best, i - j + 1)
    return best >= 0.7 * len(starts)


# ---------------------------------------------------------------- DOCX

def _paragraph_text(paragraph):
    text = paragraph.text.strip()
    if not text:
        return ""
    ppr = paragraph._p.pPr
    is_list = (ppr is not None and ppr.numPr is not None) or (
        paragraph.style is not None
        and (paragraph.style.name or "").lower().startswith("list")
    )
    if is_list and not text.startswith(("•", "-", "–", "●", "▪", "*")):
        return "• " + text
    return text


def _read_docx(path):
    try:
        doc = Document(path)
    except Exception as exc:
        raise ExtractionError(
            "This DOCX file could not be opened. It may be damaged or not a real Word document."
        ) from exc

    body = doc.element.body
    seen, lines = set(), []

    def add_unique(text):
        text = text.strip()
        if text and text not in seen:
            seen.add(text)
            lines.append(text)

    # Header text (contact details are often placed here) and text boxes first
    for section in doc.sections:
        for p in section.header.paragraphs:
            add_unique(p.text)
    for box in body.iter(qn("w:txbxContent")):
        add_unique(" ".join(t.text for t in box.iter(qn("w:t")) if t.text))

    tables = 0
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            text = _paragraph_text(Paragraph(child, doc))
            if text:
                lines.append(text)
        elif child.tag == qn("w:tbl"):
            tables += 1
            for row in Table(child, doc).rows:
                cells, done = [], set()
                for cell in row.cells:
                    if id(cell._tc) in done:        # merged cells repeat
                        continue
                    done.add(id(cell._tc))
                    cell_text = " ".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    lines.append(" | ".join(cells))

    text_boxes = len(list(body.iter(qn("w:txbxContent"))))
    multi = False
    for section in doc.sections:
        for cols in section._sectPr.xpath("./w:cols"):
            num = cols.get(qn("w:num"))
            if num and num.isdigit() and int(num) > 1:
                multi = True

    meta = {
        "pages": None,
        "tables": tables,
        "images": 0,
        "text_boxes": text_boxes,
        "multi_column": multi,
    }
    return "\n".join(lines), meta