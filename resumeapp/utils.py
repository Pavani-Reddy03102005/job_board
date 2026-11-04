import re


def clean_text(text):
    """
    Normalise whitespace but KEEP line breaks.

    The previous version replaced every newline with a space, which destroyed
    section headings and bullet points. Spaces/tabs inside a line are collapsed,
    and runs of blank lines are reduced to one.
    """
    text = (text or "").replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lines = [re.sub(r"[ \u00a0]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()