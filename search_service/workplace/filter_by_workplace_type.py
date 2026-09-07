import asyncio
import logging

from dataclasses import dataclass

from search_service.brightdata_api_schema.linkedin_jobs_input import WorkplaceType
from search_service.workplace.classify_by_rules import classify_by_rules
from search_service.workplace.classify_by_llm import classify_by_llm

logger = logging.getLogger("workplace_filter")


@dataclass
class WorkplaceFilterStats:
    total: int
    kept: int
    by_rules: int
    by_llm: int
    unknown: int


async def filter_by_workplace_type(
    *,
    documents: list[dict],
    requested: WorkplaceType,
    openai_token: str,
    openai_model: str,
) -> tuple[list[dict], WorkplaceFilterStats]:
    """
    Keep only the postings whose work format matches `requested`.

    Bright Data ignores the `remote` search filter and returns no work
    format field, so the format is derived from the posting text: cheap
    rules first, the LLM for whatever is left. Postings that stay
    unclassified are dropped rather than shown as a match.
    """

    workplace_types = [classify_by_rules(document) for document in documents]

    by_rules = sum(workplace_type is not None for workplace_type in workplace_types)

    pending = [
        index
        for index, workplace_type in enumerate(workplace_types)
        if workplace_type is None
    ]

    if pending:
        resolved = await asyncio.to_thread(
            classify_by_llm,
            documents=[documents[index] for index in pending],
            openai_token=openai_token,
            openai_model=openai_model,
        )

        for index, workplace_type in zip(pending, resolved):
            workplace_types[index] = workplace_type

    kept = [
        document
        for document, workplace_type in zip(documents, workplace_types)
        if workplace_type == requested
    ]

    stats = WorkplaceFilterStats(
        total=len(documents),
        kept=len(kept),
        by_rules=by_rules,
        by_llm=len(pending) - sum(
            workplace_types[index] is None for index in pending
        ),
        unknown=sum(workplace_type is None for workplace_type in workplace_types),
    )

    logger.info(
        "Workplace filter %s: kept %s of %s (rules %s, llm %s, unknown %s)",
        requested, stats.kept, stats.total,
        stats.by_rules, stats.by_llm, stats.unknown,
    )

    return kept, stats
