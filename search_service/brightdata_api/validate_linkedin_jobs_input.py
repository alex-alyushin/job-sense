from pydantic import ValidationError

from search_service.brightdata_api_schema.linkedin_jobs_input import LinkedInJobsInput


def validate_brightdata_linkedin_jobs_input(search_input: str):
    try:
        return LinkedInJobsInput.model_validate_json(search_input)

    except ValidationError:
        return None
