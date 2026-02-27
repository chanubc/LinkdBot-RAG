from app.application.models.llm import LLMTool

KNOWLEDGE_AGENT_PROMPT = """\
You are a personal knowledge base assistant.
Answer questions based on the user's saved links and memos.
Use the available tools to search for relevant information and provide accurate, helpful answers.\
"""

TOOLS = [
    LLMTool(
        name="search_knowledge_base",
        description="Search relevant content from the user's saved links and memos.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search question or keywords",
                }
            },
            "required": ["query"],
        },
    ),
    LLMTool(
        name="get_unread_links",
        description="Retrieve the list of unread saved links.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of links to retrieve (default: 5)",
                }
            },
            "required": [],
        },
    ),
]
