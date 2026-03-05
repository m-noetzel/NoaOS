"""Search provider implementations for the Web Search tool.

Provider-agnostic design — new providers can be added as drop-in
implementations of the SearchProvider ABC.
"""

from noa.tools.search_providers.base import SearchProvider

__all__ = ["SearchProvider"]
