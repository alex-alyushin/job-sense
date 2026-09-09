import json

from enum import StrEnum
from pydantic import BaseModel, Field, field_validator

from workplace.workplace_type import WorkplaceType, normalize_workplace_type


class ExperienceLevel(StrEnum):
    INTERNSHIP = "Internship"
    ENTRY_LEVEL = "Entry level"
    ASSOCIATE = "Associate"
    MID_SENIOR_LEVEL = "Mid-Senior level"
    DIRECTOR = "Director"
    EXECUTIVE = "Executive"


class JobType(StrEnum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    TEMPORARY = "Temporary"
    VOLUNTEER = "Volunteer"
    INTERNSHIP = "Internship"
    OTHER = "Other"


class TimeRange(StrEnum):
    PAST_24_HOURS = "Past 24 hours"
    PAST_WEEK = "Past week"
    PAST_MONTH = "Past month"
    ANY_TIME = "Any time"


class LinkedInJobsInput(BaseModel):
    """
    Discover LinkedIn jobs by keyword
    Use the Bright Data Web Scraper API to discover LinkedIn Jobs by Keyword.
    Calls the POST /datasets/v3/scrape endpoint and returns a snapshot ID.

    Documentation:
    https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-discover-by-keyword
    """

    location: str = Field(
        description="Collect jobs in a specific location"
    )

    keyword: str | None = Field(
        description=(
            "Collect new jobs by keyword search like the job title, "
            "for example: Product Manager. Utilize quotation marks "
            "around specific words or phrases to ensure an exact match."
        ),
        default=None
    )

    country: str | None = Field(
        description="Use country code with 2 letters like US or FR",
        default=None
    )

    time_range: TimeRange | None = Field(
        description="Time range of the job posting",
        default=None
    )

    job_type: JobType | None = Field(
        description="Collect jobs from specific type like Full-time or Part-time",
        default=None
    )

    experience_level: ExperienceLevel | None = Field(
        description="Collect jobs from a specific experience level",
        default=None
    )

    remote: WorkplaceType | None = Field(
        description=(
            "Set this whenever the user states a work format preference. "
            "Bright Data ignores it when collecting jobs, so the postings "
            "are checked against it afterwards and the ones with a "
            "different work format are left out of the report."
        ),
        default=None
    )

    company: str | None = Field(
        description="Collect jobs from a specific company",
        default=None
    )

    selective_search: bool = Field(
        description="When set to true, the filter will exclude titles that do not contain the specified keywords",
        default=False
    )

    jobs_to_not_include: list[str] = Field(
        description="Jobs IDs to exclude",
        default=[]
    )

    location_radius: str | None = Field(
        description=(
            "Optional radius around `location` to broaden the search. "
            "Bright Data does not document the exact format or units for "
            "this field, so leave it unset unless the user explicitly asks "
            "for a wider or narrower search area."
        ),
        default=None
    )

    @field_validator("remote", mode="before")
    @classmethod
    def _normalize_remote(cls, value):
        """
        Accept casing and spelling variants ("remote", "on site", "ON-SITE")
        so a sloppy tool call narrows the search instead of failing it.
        """

        if not isinstance(value, str) or not value.strip():
            return None

        return normalize_workplace_type(value) or value


schema_brightdata_linkedin = LinkedInJobsInput.model_json_schema()
