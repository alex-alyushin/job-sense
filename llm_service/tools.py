from search_service.brightdata_api_schema.linkedin_jobs_input import schema_brightdata_linkedin

TOOLS = [
    {
        "type": "function",
        "name": "store_user_cv",
        "description": (
            "Persist the user's resume (CV) content. Call this once, as soon "
            "as the current user message contains resume content, before "
            "doing anything else in your reply. Pass the resume text exactly "
            "as provided by the user, without modification, summarization, "
            "or reformatting. Returns {\"status\": ...}; briefly tell the "
            "user whether the save succeeded or failed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": (
                        "The full resume text exactly as provided by the "
                        "user, verbatim, with no modification or "
                        "summarization."
                    )
                }
            },
            "required": ["content"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "search_linkedin_jobs",
        "description": (
            "Start an asynchronous LinkedIn job search using the search "
            "profile collected so far. Call this ONLY after the user has "
            "explicitly confirmed they want to search now. This call does "
            "not return a result in this turn — in the same reply where "
            "you call it, tell the user the search has started and "
            "results will follow shortly, without waiting for any tool "
            "output. If the search parameters are invalid, you will not "
            "be notified — the application handles that directly with "
            "the user, so there is nothing for you to retry. Call it "
            "once per confirmed search intent."
        ),
        "parameters": schema_brightdata_linkedin,
    }
]
