from enum import StrEnum


class WorkplaceType(StrEnum):
    REMOTE = "Remote"
    ON_SITE = "On-site"
    HYBRID = "Hybrid"


def normalize_workplace_type(value) -> WorkplaceType | None:
    """
    Read a work format out of a free-form string ("remote", "on site",
    "ON-SITE"), so a sloppy tool call or a stored attribute still narrows
    the search instead of failing it. Returns None when nothing matches.
    """

    if isinstance(value, WorkplaceType):
        return value

    if not isinstance(value, str):
        return None

    normalized = value.strip().casefold().replace(" ", "-")

    if normalized == "onsite":
        return WorkplaceType.ON_SITE

    for workplace_type in WorkplaceType:
        if normalized == workplace_type.casefold().replace(" ", "-"):
            return workplace_type

    return None
