import json

from enum import StrEnum
from pydantic import BaseModel, Field


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
            "Collect new jobs by keyword search like the job title,"
            "for example: Product Manager. Utilize quotation marks"
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

    remote: str | None = Field(
        description="Specify if you want to collect only “Remote”, “On-site” or “Hybrid” jobs",
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

    location_radius: str | None = Field(default=None)


schema_brightdata_linkedin = LinkedInJobsInput.model_json_schema()
