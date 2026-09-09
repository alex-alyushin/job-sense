import re

from workplace.workplace_type import WorkplaceType
from workplace.document_text import extract_document_text


# On-site is matched first: phrases like "not a remote position" would
# otherwise be read as a remote posting.
ON_SITE_PATTERNS = [
    r"on[-\s]?site\s+(?:position|role|job|only|required)",
    r"must\s+(?:be|work)\s+on[-\s]?site",
    r"\bin[-\s]office\b",
    r"no\s+remote\s+work",
    r"not\s+a\s+remote\s+(?:position|role|job)",
    r"remote\s+work\s+is\s+not",
]

HYBRID_PATTERNS = [
    r"\bhybrid\b",
]

# A bare "remote" is deliberately absent: it also shows up in "remote teams"
# and "remote systems". Ambiguous postings are left to the LLM instead.
REMOTE_PATTERNS = [
    r"100\s*%\s*remote",
    r"fully\s+remote",
    r"remote[-\s]first",
    r"work\s+from\s+home",
    r"telecommut\w*",
    r"remote\s+(?:position|role|job|opportunity)",
    r"(?:position|role|job)\s+is\s+remote",
]

RULES = [
    (WorkplaceType.ON_SITE, [re.compile(p, re.IGNORECASE) for p in ON_SITE_PATTERNS]),
    (WorkplaceType.HYBRID, [re.compile(p, re.IGNORECASE) for p in HYBRID_PATTERNS]),
    (WorkplaceType.REMOTE, [re.compile(p, re.IGNORECASE) for p in REMOTE_PATTERNS]),
]


def classify_by_rules(document: dict) -> WorkplaceType | None:
    """
    Decide the work format from unambiguous phrases in the posting.
    Returns None when nothing conclusive is found, so the caller can fall
    back to the LLM.
    """

    text = extract_document_text(document)

    for workplace_type, patterns in RULES:
        if any(pattern.search(text) for pattern in patterns):
            return workplace_type

    return None
