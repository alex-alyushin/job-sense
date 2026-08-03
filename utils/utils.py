import json
import fitz


def is_json(value):
    try:
        json.loads(value)
        return True
    except:
        return False


def truncate(text, max_length=100, flat=False):
    ELLIPSIS = "..."

    if text is None:
        return None

    if len(text) > max_length:
        text = text[:(max_length - 3)] + ELLIPSIS

    if flat:
        text = text.replace("\r\n", " ").replace("\n", " ")

    return text


async def read_pdf(file_stream) -> str:
    parsed_text = ""

    for page in fitz.open(stream=file_stream, filetype="pdf"):
        parsed_text += page.get_text()

    return parsed_text


async def read_file(file_stream, mime_type, file_name) -> str | None:
    if mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
        return await read_pdf(file_stream)

    return None
