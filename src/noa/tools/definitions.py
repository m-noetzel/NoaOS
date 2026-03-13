"""Tool definitions for LLM function calling.

Provides JSON Schema tool definitions in both Anthropic and OpenAI
formats. Only tools registered in the gateway (with credentials) are
included.
"""

from __future__ import annotations

from typing import Any

# Canonical tool definitions: name → {description, functions}
# Each function has: description, parameters (JSON Schema)
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "web_search": {
        "description": "Search the web for current information.",
        "functions": {
            "web_search": {
                "description": (
                    "Search the web and return results with titles, "
                    "URLs, and snippets."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return.",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
        },
    },
    "calendar": {
        "description": "Manage Google Calendar events.",
        "functions": {
            "list_events": {
                "description": (
                    "List calendar events within a date range."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "Start date (ISO format).",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date (ISO format).",
                        },
                    },
                    "required": ["start_date", "end_date"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
            "create_event": {
                "description": "Create a new calendar event.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Event title.",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time (ISO format).",
                        },
                        "end": {
                            "type": "string",
                            "description": "End time (ISO format).",
                        },
                        "description": {
                            "type": "string",
                            "description": "Event description.",
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Attendee email addresses.",
                        },
                    },
                    "required": ["title", "start", "end"],
                },
                "risk_tier": "medium",
                "domain": "external",
            },
        },
    },
    "gmail": {
        "description": "Search and send emails via Gmail.",
        "functions": {
            "search_emails": {
                "description": "Search emails by query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results.",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
            "read_email": {
                "description": "Read full email content by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "Email ID to read.",
                        },
                    },
                    "required": ["email_id"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
            "send_email": {
                "description": "Send an email.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject.",
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body text.",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
                "risk_tier": "medium",
                "domain": "external",
            },
            "draft_email": {
                "description": "Create an email draft.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject.",
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body text.",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
        },
    },
    "notion": {
        "description": "Search and manage Notion pages.",
        "functions": {
            "search_pages": {
                "description": "Search Notion pages by query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query.",
                        },
                    },
                    "required": ["query"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
            "read_page": {
                "description": "Read a Notion page by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Page ID to read.",
                        },
                    },
                    "required": ["page_id"],
                },
                "risk_tier": "low",
                "domain": "external",
            },
            "create_page": {
                "description": "Create a new Notion page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_id": {
                            "type": "string",
                            "description": "Parent page ID.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Page content (markdown).",
                        },
                    },
                    "required": ["parent_id", "title", "content"],
                },
                "risk_tier": "medium",
                "domain": "external",
            },
        },
    },
    "memory": {
        "description": "Remember and recall facts about the user.",
        "functions": {
            "remember": {
                "description": (
                    "Store a fact about the user for long-term memory. "
                    "Use when the user shares preferences, habits, "
                    "important dates, or personal information they want "
                    "you to remember across conversations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "description": "The fact to remember.",
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Category: preference, habit, contact, "
                                "context, or general."
                            ),
                            "default": "general",
                        },
                        "source_thread_id": {
                            "type": "string",
                            "description": "Thread ID where the fact originated.",
                            "default": "",
                        },
                    },
                    "required": ["fact", "category"],
                },
                "risk_tier": "low",
                "domain": "private",
            },
            "recall": {
                "description": (
                    "Search stored facts about the user. "
                    "Use when you need to retrieve previously "
                    "remembered information."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for facts.",
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Max results to return.",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                "risk_tier": "low",
                "domain": "private",
            },
        },
    },
}


def get_anthropic_tools(
    registered: list[str],
) -> list[dict[str, Any]]:
    """Build Anthropic-format tool definitions.

    Each tool function becomes a separate tool entry since Anthropic
    uses flat tool names (no nested tool.function).

    Format: {"name": "tool__function", "description": ..., "input_schema": ...}
    """
    tools: list[dict[str, Any]] = []
    for tool_name in registered:
        schema = TOOL_SCHEMAS.get(tool_name)
        if schema is None:
            continue
        for func_name, func_def in schema["functions"].items():
            tools.append({
                "name": f"{tool_name}__{func_name}",
                "description": func_def["description"],
                "input_schema": func_def["parameters"],
            })
    return tools


def get_openai_tools(
    registered: list[str],
) -> list[dict[str, Any]]:
    """Build OpenAI-format tool definitions.

    Format: {"type": "function", "function": {"name": ..., ...}}
    """
    tools: list[dict[str, Any]] = []
    for tool_name in registered:
        schema = TOOL_SCHEMAS.get(tool_name)
        if schema is None:
            continue
        for func_name, func_def in schema["functions"].items():
            tools.append({
                "type": "function",
                "function": {
                    "name": f"{tool_name}__{func_name}",
                    "description": func_def["description"],
                    "parameters": func_def["parameters"],
                },
            })
    return tools


def parse_tool_call_name(
    name: str,
) -> tuple[str, str]:
    """Parse 'tool__function' back into (tool_name, function_name).

    Falls back to treating the whole name as a legacy flat name.
    """
    if "__" in name:
        parts = name.split("__", 1)
        return parts[0], parts[1]
    return name, name
