# Utility Tools

This directory contains utility scripts and tools for development, testing, and debugging of the sgraph-mcp-server project.

## Directory Structure

```
tools/
├── analysis/           # Model analysis utilities
├── testing/            # Component testing utilities  
├── debugging/          # Debugging and diagnostic tools
└── README.md          # This file
```

## Available Tools

### Analysis Tools (`analysis/`)

**`check_model_freshness.py`**
- Analyzes sgraph models for freshness indicators
- Checks for modular architecture components
- Validates recent analysis outputs
- Usage: `python tools/analysis/check_model_freshness.py [model_path]`

### Testing Tools (`testing/`)

**`test_modular_components.py`** 
- Tests modular component imports and functionality
- Validates service isolation and integration
- Useful for architecture validation
- Usage: `python tools/testing/test_modular_components.py [--model path]`

### Debugging Tools (`debugging/`)

**`mcp_connection_test.py`**
- Comprehensive MCP connection diagnostics
- Tests server connectivity, Node.js compatibility
- Validates mcp-remote functionality
- Usage: `python tools/debugging/mcp_connection_test.py [--url server_url]`

## Usage Examples

### Check Model Freshness
```bash
# Check default model
python tools/analysis/check_model_freshness.py

# Check specific model
python tools/analysis/check_model_freshness.py /path/to/model.xml.zip

# JSON output
python tools/analysis/check_model_freshness.py --json
```

### Test Modular Components
```bash
# Test with default model
python tools/testing/test_modular_components.py

# Test with specific model
python tools/testing/test_modular_components.py --model /path/to/model.xml.zip
```

### Debug MCP Connection
```bash
# Test default server
python tools/debugging/mcp_connection_test.py

# Test specific server
python tools/debugging/mcp_connection_test.py --url http://localhost:8008/sse

# JSON output for automation
python tools/debugging/mcp_connection_test.py --json
```

## Tool Design Principles

### 1. **Self-Contained**
- Each tool is a standalone script
- Minimal dependencies on project structure
- Can be run from any directory

### 2. **Informative Output**
- Clear, structured output with status indicators
- Both human-readable and JSON formats supported
- Comprehensive error messages and suggestions

### 3. **Robust Error Handling**
- Graceful handling of missing files/servers
- Timeout protection for network operations
- Detailed diagnostic information

### 4. **Configurable**
- Command-line arguments for customization
- Sensible defaults for common use cases
- Environment-aware configuration

## Integration with Main Project

These tools complement the main project structure:

- **Analysis tools** work with the modular service layer
- **Testing tools** validate the architecture we've built
- **Debugging tools** help with MCP server troubleshooting

They use the same modular components but are designed for developer/AI use rather than end-user functionality.

## Development Guidelines

When adding new tools:

1. **Choose appropriate directory** based on tool purpose
2. **Follow naming convention**: descriptive, snake_case names
3. **Include comprehensive docstrings** and help text
4. **Add error handling** and timeout protection
5. **Support both interactive and automated use** (JSON output)
6. **Update this README** with tool description

## Relationship to throwaway-ai-code/

The `throwaway-ai-code/` directory is for temporary AI debugging scripts, while this `tools/` directory is for:

- **Permanent utilities** that might be needed again
- **Reusable scripts** for common development tasks  
- **Production-quality tools** with proper error handling
- **Documented utilities** that other developers can use

Scripts graduate from `throwaway-ai-code/` to `tools/` when they prove useful and are cleaned up for reuse.

