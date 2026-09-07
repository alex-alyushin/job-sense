import re
import html

HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")

TEXT_FIELDS = [
    "job_title",
    "job_location",
    "job_summary",
    "job_description_formatted",
]


def extract_document_text(document: dict) -> str:
    """
    Flatten the fields that may mention the work format into plain text.
    `job_description_formatted` is HTML, so tags and entities are stripped.
    """

    parts = [document.get(field) or "" for field in TEXT_FIELDS]

    text = HTML_TAG.sub(" ", html.unescape(" ".join(parts)))

    return WHITESPACE.sub(" ", text).strip()
