from app.application.models.llm import LLMTool

KNOWLEDGE_AGENT_PROMPT = """\
You are a personal knowledge base assistant.
Answer questions based on the user's saved links and memos.
Use the available tools to search for relevant information and provide accurate, helpful answers.\
"""

TOOLS = [
    LLMTool(
        name="search_knowledge_base",
        description=(
            "Search for content by keyword or topic from ALL saved links and memos "
            "(including already-read ones). Use for questions about specific topics, "
            "or when the user asks to find or list saved content."
        ),
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
        description=(
            "Retrieve UNREAD saved links only. "
            "Use ONLY when the user explicitly asks about unread or new links they haven't read yet."
        ),
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
