"""
Legacy profile - backwards compatible with original 14-tool set.

This profile registers all existing tools for backwards compatibility.
Use this profile when migrating from the original server or when you
need access to all available tools.

Consider using claude-code profile for better token efficiency.
"""

from mcp.server.fastmcp import FastMCP

from src.profiles import register_profile
from src.tools import model_tools, search_tools, analysis_tools, navigation_tools


@register_profile("legacy")
class LegacyProfile:
    """Legacy profile with all 13 original tools.

    Tools included:
    - Model: sgraph_load_model, sgraph_get_model_overview
    - Search: sgraph_search_elements_by_name, sgraph_get_elements_by_type,
              sgraph_search_elements_by_attributes
    - Analysis: sgraph_get_subtree_dependencies, sgraph_get_dependency_chain,
                sgraph_get_multiple_elements, sgraph_analyze_external_usage,
                sgraph_get_high_level_dependencies
    - Navigation: sgraph_get_root_element, sgraph_get_element,
                  sgraph_get_element_incoming_associations,
                  sgraph_get_element_outgoing_associations
    """

    name = "legacy"
    description = "All 13 original tools - backwards compatible"

    def register_tools(self, mcp: FastMCP) -> None:
        """Register all original tools with the MCP server."""
        model_tools.register_tools(mcp)
        search_tools.register_tools(mcp)
        analysis_tools.register_tools(mcp)
        navigation_tools.register_tools(mcp)
