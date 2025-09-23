# SGraph-MCP-Server Architecture

## Overview

The sgraph-mcp-server has been designed with a modular architecture that separates concerns, improves testability, and enhances maintainability. This document describes the current architectural patterns and design decisions.

## Architecture Principles

### 1. **Single Responsibility Principle**
Each module has one clear purpose:
- **Core**: Fundamental components (model management, data conversion)
- **Services**: Business logic (search, dependency analysis, overview generation)
- **Tools**: MCP tool definitions and request/response handling
- **Utils**: Cross-cutting concerns (logging, validation)

### 2. **Dependency Inversion**
- Services depend on abstractions, not concrete implementations
- Tools depend on services, not directly on data structures
- Clear separation between business logic and presentation layer

### 3. **Testability by Design**
- Each layer can be tested independently
- Service logic is separated from MCP protocol concerns
- Minimal external dependencies in core business logic

## Directory Structure

```
src/
├── core/                   # Core components
│   ├── model_manager.py    # Model loading and caching
│   └── element_converter.py # Element-to-dict conversions
├── services/               # Business logic layer
│   ├── search_service.py   # Search algorithms
│   ├── dependency_service.py # Dependency analysis
│   └── overview_service.py # Model structure analysis
├── tools/                  # MCP tool definitions
│   ├── model_tools.py      # Model management tools
│   ├── search_tools.py     # Search-related tools
│   ├── analysis_tools.py   # Dependency analysis tools
│   └── navigation_tools.py # Element navigation tools
└── utils/                  # Utilities
    ├── logging.py          # Centralized logging
    └── validators.py       # Input validation

tests/
├── unit/                   # Unit tests
├── integration/            # Integration tests
└── performance/            # Performance tests

throwaway-ai-code/          # Temporary AI debugging code
```

## Component Responsibilities

### Core Layer (`src/core/`)

**ModelManager** (`model_manager.py`)
- Loads sgraph models from files
- Manages model caching in memory
- Handles model lifecycle (load, get, remove, clear)
- Provides comprehensive logging and error handling

**ElementConverter** (`element_converter.py`)
- Converts SElement objects to dictionary representations
- Handles batch conversions
- Manages association serialization

### Service Layer (`src/services/`)

**SearchService** (`search_service.py`)
- Implements search algorithms (by name, type, attributes)
- Uses iterative traversal for performance
- Handles regex and glob pattern matching
- Supports scoped searches

**DependencyService** (`dependency_service.py`)
- Analyzes dependency chains and subtrees
- Provides transitive dependency analysis
- Supports multiple element retrieval
- Handles both incoming and outgoing dependencies

**OverviewService** (`overview_service.py`)
- Generates hierarchical model overviews
- Provides statistics and type distribution
- Supports configurable depth analysis
- Optimized for quick structural understanding

### Tools Layer (`src/tools/`)

**Model Tools** (`model_tools.py`)
- `sgraph_load_model`: Load models with validation
- `sgraph_get_model_overview`: Hierarchical structure overview

**Search Tools** (`search_tools.py`)
- `sgraph_search_elements_by_name`: Pattern-based search
- `sgraph_get_elements_by_type`: Type-based filtering
- `sgraph_search_elements_by_attributes`: Attribute-based search

**Analysis Tools** (`analysis_tools.py`)
- `sgraph_get_subtree_dependencies`: Subtree dependency analysis
- `sgraph_get_dependency_chain`: Transitive dependency chains
- `sgraph_get_multiple_elements`: Bulk element retrieval

**Navigation Tools** (`navigation_tools.py`)
- `sgraph_get_root_element`: Root element access
- `sgraph_get_element`: Single element retrieval
- `sgraph_get_element_*_associations`: Association navigation

### Utils Layer (`src/utils/`)

**Logging** (`logging.py`)
- Centralized logging configuration
- Service-specific logger management
- Consistent log formatting

**Validators** (`validators.py`)
- Model ID validation
- Path validation and security checks
- Pattern validation for search operations
- Element type validation

## Data Flow

```
MCP Client Request
       ↓
[Tools Layer] - Validates input, calls services
       ↓
[Services Layer] - Implements business logic
       ↓
[Core Layer] - Manages models and data conversion
       ↓
SGraph Library - Actual graph operations
```

## Performance Characteristics

### Optimizations Implemented

1. **Iterative Traversal**: All tree/graph traversals use iterative approaches instead of recursion
2. **Model Caching**: Models are loaded once and cached in memory
3. **Lazy Loading**: Only requested data is processed and converted
4. **Bulk Operations**: Multiple element operations are batched for efficiency

### Performance Targets

- **Model Loading**: < 60 seconds (with timeout)
- **Search Operations**: < 100ms for typical queries
- **Overview Generation**: < 150ms for depth ≤ 5
- **Dependency Analysis**: < 200ms for moderate subtrees

## Error Handling Strategy

### 1. **Layered Error Handling**
- **Tools Layer**: Catches all exceptions, returns error objects
- **Services Layer**: Logs business logic errors, raises specific exceptions
- **Core Layer**: Handles system-level errors (file I/O, timeouts)

### 2. **Error Response Format**
```json
{
  "error": "Human-readable error message",
  "details": "Optional technical details"
}
```

### 3. **Logging Strategy**
- **DEBUG**: Detailed operation traces
- **INFO**: Important state changes and metrics
- **WARNING**: Recoverable issues
- **ERROR**: Failures that prevent operation completion

## Testing Strategy

### 1. **Unit Tests** (`tests/unit/`)
- Test individual components in isolation
- Mock external dependencies
- Focus on business logic correctness

### 2. **Integration Tests** (`tests/integration/`)
- Test component interactions
- End-to-end workflows
- Real model loading and analysis

### 3. **Performance Tests** (`tests/performance/`)
- Validate performance targets
- Regression testing for optimizations
- Real-world scenario simulation

## Extension Points

### Adding New Tools
1. Create tool class in appropriate `tools/` module
2. Use `@mcp.tool()` decorator
3. Implement validation and error handling
4. Add corresponding service method if needed

### Adding New Services
1. Create service class in `services/`
2. Implement static methods for operations
3. Add comprehensive logging
4. Create unit tests

### Adding New Validators
1. Add validation function to `utils/validators.py`
2. Use in tool layer for input validation
3. Add unit tests for edge cases

## Migration Notes

### From Monolithic to Modular

The original `server.py` (350+ lines) has been refactored into:
- **Tools**: 4 focused modules (~100 lines each)
- **Services**: 3 business logic modules (~150 lines each)
- **Core**: 2 fundamental modules (~100 lines each)
- **Utils**: 2 utility modules (~50 lines each)

### Benefits Achieved

1. **Maintainability**: Clear boundaries, easier to modify
2. **Testability**: Each component can be tested independently
3. **Extensibility**: New features don't require touching core logic
4. **Performance**: Services can be optimized individually
5. **Reusability**: Core services work outside MCP context

## Future Architectural Considerations

### 1. **Plugin Architecture**
Consider implementing a plugin system for:
- Custom search algorithms
- Additional analysis tools
- External data source integrations

### 2. **Caching Enhancements**
- Persistent model caching
- Query result caching
- Cache invalidation strategies

### 3. **Parallel Processing**
- Async service operations
- Parallel dependency analysis
- Concurrent model loading

### 4. **Configuration Management**
- External configuration files
- Environment-specific settings
- Runtime configuration updates
