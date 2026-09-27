# User Agent Parser
"""Public surface for the user_agent_parser package.

Only `parse` is exported. Keeping the surface tiny means callers cannot
accidentally depend on internal helpers that change between releases.
"""

from .core import parse, parse_user_agent, UserAgentResult

__all__ = ["parse", "parse_user_agent", "UserAgentResult"]
