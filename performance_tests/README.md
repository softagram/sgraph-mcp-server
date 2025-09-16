# Performance Tests

This directory contains performance tests for the SGraph MCP Server to ensure that search operations meet performance requirements.

## Test Files

- `test_search_performance.py` - Tests the performance of `sgraph_search_elements_by_name`
- `run_tests.py` - Test runner that executes all performance tests
- `__init__.py` - Package initialization file

## Running Tests

### Run Individual Test

```bash
cd /path/to/sgraph-mcp-server
uv run python performance_tests/test_search_performance.py
```

### Run All Tests

```bash
cd /path/to/sgraph-mcp-server
uv run python performance_tests/run_tests.py
```

## Test Details

### Search Performance Test

**Test**: `test_search_performance.py`

**Purpose**: Verify that `sgraph_search_elements_by_name` can efficiently search large models.

**Test Case**:
- **Model**: `langchain.xml.zip` (large real-world codebase)
- **Target Element**: `ConstitutionalPrinciple` (class)
- **Expected Path**: `/langchain-ai/langchain/libs/langchain/langchain/chains/constitutional_ai/models.py/ConstitutionalPrinciple`
- **Performance Requirement**: Search must complete within 100ms
- **Correctness Requirement**: Must find the target element correctly

**Typical Results**:
- Model Loading: ~700-800ms (one-time cost)
- Search Duration: ~11ms (well under 100ms limit)
- Elements Found: 1 (the target ConstitutionalPrinciple class)

## Performance Benchmarks

| Operation | Duration | Requirement | Status |
|-----------|----------|-------------|--------|
| Model Loading | ~750ms | N/A (one-time) | ✅ |
| Name Search | ~11ms | < 100ms | ✅ |

## Adding New Tests

To add a new performance test:

1. Create a new test function in the appropriate test file
2. Follow the naming convention: `test_<operation>_performance`
3. Include both performance and correctness assertions
4. Add the test to `run_tests.py` if it's a new test file
5. Update this README with test details

## Test Data

The tests use the `langchain.xml.zip` model located in `sgraph-example-models/`. This model contains:
- Real-world Python codebase structure
- Thousands of elements across multiple files
- Complex dependency relationships
- Representative of typical large software projects

This makes it ideal for performance testing as it reflects real-world usage scenarios.
