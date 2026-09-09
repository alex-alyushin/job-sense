from workplace.workplace_type import WorkplaceType
from workplace.document_text import extract_document_text

MAX_TEXT_LENGTH = 2000

UNKNOWN = "Unknown"

SCHEMA_NAME = "workplace_types"

INSTRUCTIONS = (
    "You classify the work format of LinkedIn job postings.\n\n"
    "For each posting decide whether it is:\n"
    "- Remote: the work is done from anywhere, no regular office attendance;\n"
    "- Hybrid: office attendance is required for part of the week;\n"
    "- On-site: the work requires being at a workplace;\n"
    "- Unknown: the posting does not say.\n\n"
    "The `location` field is the employer's city and is present even for "
    "remote postings, so never infer On-site from it alone. Judge only by "
    "what the posting states. Prefer Unknown over guessing.\n\n"
    "Return one entry for every posting, using the given id."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "workplace_type": {
                        "type": "string",
                        "enum": [
                            WorkplaceType.REMOTE,
                            WorkplaceType.HYBRID,
                            WorkplaceType.ON_SITE,
                            UNKNOWN,
                        ],
                    },
                },
                "required": ["id", "workplace_type"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def build_classification_input(documents: list[tuple[int, dict]]) -> list[dict]:
    """
    Reduce the postings to the few fields that carry the work format, so the
    request stays small enough to classify a whole search in one call.
    `documents` is a list of (document id, Bright Data document) pairs; the
    id comes back with the answer and maps it to the posting.
    """

    return [
        {
            "id": document_id,
            "title": document.get("job_title") or "",
            "location": document.get("job_location") or "",
            "text": extract_document_text(document)[:MAX_TEXT_LENGTH],
        }
        for document_id, document in documents
    ]


def parse_classification_output(output) -> dict[int, WorkplaceType]:
    """
    Read the classified ids out of the LLM answer, skipping anything that is
    not a work format we asked for (`Unknown` included).
    """

    workplace_types: dict[int, WorkplaceType] = {}

    if not isinstance(output, dict):
        return workplace_types

    for result in output.get("results") or []:
        if not isinstance(result, dict):
            continue

        document_id = result.get("id")
        value = result.get("workplace_type")

        if not isinstance(document_id, int):
            continue

        if value in tuple(WorkplaceType):
            workplace_types[document_id] = WorkplaceType(value)

    return workplace_types
