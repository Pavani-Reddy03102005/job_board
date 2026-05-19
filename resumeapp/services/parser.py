import pdfplumber

from docx import Document


def extract_pdf_text(path):

    text = ""

    with pdfplumber.open(path) as pdf:

        for page in pdf.pages:

            extracted = page.extract_text()

            if extracted:

                text += extracted

    return text


def extract_docx_text(path):

    doc = Document(path)

    text = ""

    for para in doc.paragraphs:

        text += para.text

    return text