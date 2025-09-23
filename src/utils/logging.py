"""
Centralized logging configuration for sgraph-mcp-server.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """Set up centralized logging configuration."""
    
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Set specific loggers
    logging.getLogger("sgraph_helper").setLevel(numeric_level)
    logging.getLogger("model_manager").setLevel(numeric_level)
    logging.getLogger("search_service").setLevel(numeric_level)
    logging.getLogger("dependency_service").setLevel(numeric_level)
    logging.getLogger("overview_service").setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with consistent configuration."""
    return logging.getLogger(name)
