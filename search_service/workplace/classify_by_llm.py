import json
import logging

from openai import OpenAI, OpenAIError

from search_service.brightdata_api_schema.linkedin_jobs_input import WorkplaceType
from search_service.workplace.document_text import extract_document_text

logger = logging.getLogger("workplace_classifier")

MAX_TEXT_LENGTH = 2000

UNKNOWN = "Unknown"

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
    "Return one entry for every posting, using the given index."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
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
                "required": ["index", "workplace_type"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def classify_by_llm(
    *,
    documents: list[dict],
    openai_token: str,
    openai_model: str,
) -> list[WorkplaceType | None]:
    """
    Classify postings the rules could not resolve, in a single request.
    Returns one entry per document, None where the answer is unusable.
    """

    if not documents:
        return []

    postings = [
        {
            "index": index,
            "title": document.get("job_title") or "",
            "location": document.get("job_location") or "",
            "text": extract_document_text(document)[:MAX_TEXT_LENGTH],
        }
        for index, document in enumerate(documents)
    ]

    try:
        response = OpenAI(api_key=openai_token).responses.create(
            model=openai_model,
            input=[
                {"role": "developer", "content": INSTRUCTIONS},
                {"role": "user", "content": json.dumps(postings, ensure_ascii=False)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "workplace_types",
                    "strict": True,
                    "schema": SCHEMA,
                }
            },
        )

        results = json.loads(response.output_text)["results"]

    except (OpenAIError, json.JSONDecodeError, KeyError, TypeError) as error:
        logger.error("Workplace classification failed: %s", error)
        return [None] * len(documents)

    workplace_types: list[WorkplaceType | None] = [None] * len(documents)

    for result in results:
        index = result.get("index")
        value = result.get("workplace_type")

        if not isinstance(index, int) or not (0 <= index < len(documents)):
            continue

        if value in tuple(WorkplaceType):
            workplace_types[index] = WorkplaceType(value)

    return workplace_types
