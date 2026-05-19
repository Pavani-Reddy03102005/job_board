def clean_text(text):

    text = text.replace("\n", " ")

    text = text.replace("\t", " ")

    return text.strip()