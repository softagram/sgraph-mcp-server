# SGraph MCP Server

## Instructions

This let's your favourite agent to integrate with [sgraph](http://github.com/softagram/sgraph|sgraph) data model. 

## Rationale

The benefit of this MCP integration is to make the agent very efficient on handling complex data. As the complex data is costly to analyze (re-analyze), it is obvious that if the complexity can be captured into a compact and understandable format, it is much more efficient for the agent to utilize the data from that format, instead of running excessive amount of e.g. grep commands over the text content or source codde files. 

## How to utilize

1. The sgraph can contain hierarchy, relationships and attributes of a large network of nodes. Implement an analyzer/parser to produce sgraph model files from your data sources.
2. Integrate the flow of models into your device, e.g. pull models when they change.
3. Configure sgrpah-mcp-server to your agent, and spawn it up.
4. Write custom rules to let your agent know about this efficient tool. This step will boost your agent and makes it automated.

## Install dependencies

```bash
uv sync
```

## Run the server

```bash
uv run src/server.py
```

## MCP client configuration

```json
{
  "mcpServers": {
    "sgraph-mcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/sse"]
    }
  }
}
```
