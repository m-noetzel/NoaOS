"""Validation helpers for custom tool registration (TM5).

Validates function definitions, auth types, and tool name conflicts
before persistence.
"""

from __future__ import annotations

from typing import Any

# Built-in tool names that custom tools must not collide with.
BUILTIN_TOOL_NAMES = frozenset({
    "calendar",
    "gmail",
    "notion",
    "web_search",
    "memory",
})

VALID_AUTH_TYPES = frozenset({"bearer", "api_key", "none"})


def validate_custom_tool_functions(functions: list[dict[str, Any]]) -> None:
    """Validate a list of function definitions for a custom tool.

    Raises ValueError or KeyError if any function is malformed.
    """
    for func in functions:
        # name is required
        if "name" not in func:
            raise KeyError("Each function must have a 'name' field")

        # parameters must have type=object
        params = func.get("parameters", {})
        if params.get("type") != "object":
            raise ValueError(
                f"Function '{func['name']}' parameters must have type='object', "
                f"got type='{params.get('type')}'"
            )


def validate_auth_type(auth_type: str) -> None:
    """Validate that auth_type is one of the supported values.

    Raises ValueError for unsupported auth types.
    """
    if auth_type not in VALID_AUTH_TYPES:
        raise ValueError(
            f"Invalid auth_type '{auth_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_AUTH_TYPES))}"
        )


def validate_custom_tool_name(name: str) -> None:
    """Validate that a custom tool name does not collide with built-in tools.

    Raises ValueError if the name matches a built-in tool.
    """
    if name in BUILTIN_TOOL_NAMES:
        raise ValueError(
            f"Tool name '{name}' conflicts with built-in tool. "
            f"Choose a different name."
        )
