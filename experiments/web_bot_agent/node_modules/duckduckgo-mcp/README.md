# DuckDuckGo MCP

[![NPM Version](https://img.shields.io/npm/v/duckduckgo-mcp.svg?logo=npm)](https://www.npmjs.com/package/duckduckgo-mcp)

A MCP server for DuckDuckGo HTML search.

## Features

- Search DuckDuckGo HTML results
- Returns title, URL, and snippet for each result
- Caches results
- Retries on bot detection

## Usage

```bash
bunx --silent duckduckgo-mcp@latest
```

<details>
<summary>OpenCode</summary>

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "duckduckgo": {
      "enabled": true,
      "type": "local",
      "command": ["bunx", "--silent", "duckduckgo-mcp@latest"]
    }
  }
}
```

</details>

## Development

```bash
# Install dependencies
bun install --frozen-lockfile

# Type check
bun run typecheck

# Lint
bun run lint

# Format
bun run format

# Test
bun test

# Start MCP server
bun ./index.ts

# Build
bun run build
```
