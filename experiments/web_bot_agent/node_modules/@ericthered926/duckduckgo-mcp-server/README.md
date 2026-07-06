# DuckDuckGo MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides DuckDuckGo search functionality for AI assistants.

[![npm version](https://img.shields.io/npm/v/@ericthered926/duckduckgo-mcp-server.svg)](https://www.npmjs.com/package/@ericthered926/duckduckgo-mcp-server)

> **Attribution**: This project is a fork of [zhsama/duckduckgo-mcp-server](https://github.com/zhsama/duckduckgo-mcp-server), originally created by [zhsama](https://github.com/zhsama). This fork adds English localization, news search, region support, time filtering, and modern tooling.

## Features

- **Web Search** - Search the web with region-specific and time-filtered results
- **News Search** - Search recent news articles with source and date information
- **Token Optimization** - Configurable result limits, snippet truncation, and formatting for low-VRAM LLMs
- **SafeSearch** - Content filtering (strict, moderate, off)
- **Region Support** - Localized results for different countries
- **Time Filtering** - Filter results by day, week, month, year
- **Rate Limiting** - Configurable rate limits to prevent abuse
- **Configurable Logging** - Debug, info, warn, error, or none

## Installation

### Prerequisites

- Node.js >= 18.0.0 (tested with Node 24)
- npm

### Install & Build

```bash
npm install
npm run build
```

## Available Tools

### `duckduckgo_web_search`

Performs a web search using DuckDuckGo.

| Parameter    | Type   | Required | Default         | Description                                       |
| ------------ | ------ | -------- | --------------- | ------------------------------------------------- |
| `query`      | string | Yes      | -               | Search query (max 400 characters)                 |
| `limit`      | number | No       | DDG_MAX_RESULTS | Override default result limit (1-20)              |
| `count`      | number | No       | DDG_MAX_RESULTS | [Deprecated: use `limit`] Number of results       |
| `safeSearch` | string | No       | "moderate"      | Filter: "strict", "moderate", or "off"            |
| `region`     | string | No       | "wt-wt"         | Region code (e.g., "us-en", "uk-en", "de-de")     |
| `time`       | string | No       | "all"           | Time range: "day", "week", "month", "year", "all" |

**Example:**

```json
{
  "query": "TypeScript best practices",
  "count": 5,
  "region": "us-en",
  "time": "month"
}
```

### `duckduckgo_news_search`

Search for recent news articles.

| Parameter    | Type   | Required | Default         | Description                                       |
| ------------ | ------ | -------- | --------------- | ------------------------------------------------- |
| `query`      | string | Yes      | -               | News search query (max 400 characters)            |
| `limit`      | number | No       | DDG_MAX_RESULTS | Override default result limit (1-20)              |
| `count`      | number | No       | DDG_MAX_RESULTS | [Deprecated: use `limit`] Number of results       |
| `safeSearch` | string | No       | "moderate"      | Filter: "strict", "moderate", or "off"            |
| `time`       | string | No       | "all"           | Time range: "day", "week", "month", "year", "all" |

**Example:**

```json
{
  "query": "artificial intelligence",
  "count": 10,
  "time": "week"
}
```

## Supported Regions

| Code    | Region           |
| ------- | ---------------- |
| `wt-wt` | Worldwide        |
| `us-en` | United States    |
| `uk-en` | United Kingdom   |
| `ca-en` | Canada (English) |
| `au-en` | Australia        |
| `de-de` | Germany          |
| `fr-fr` | France           |
| `es-es` | Spain            |
| `it-it` | Italy            |
| `jp-jp` | Japan            |
| `br-pt` | Brazil           |
| `mx-es` | Mexico           |
| `in-en` | India            |

Other region codes following the `xx-xx` format may also work.

## Configuration

### Environment Variables

#### Token Optimization (for low-VRAM LLMs)

| Variable                  | Default | Description                                     |
| ------------------------- | ------- | ----------------------------------------------- |
| `DDG_MAX_RESULTS`         | 3       | Default number of results returned              |
| `DDG_MAX_SNIPPET_LENGTH`  | 150     | Max characters per snippet (truncated with ...) |
| `DDG_ENABLE_FULL_CONTENT` | false   | Set to "true" to disable truncation             |
| `DDG_STRIP_EMOJI`         | false   | Set to "true" to remove emojis from titles/text |
| `DDG_OUTPUT_FORMAT`       | "dense" | options: "dense", "json", "minimal"             |

#### Rate Limiting

| Variable                | Default | Description                 |
| ----------------------- | ------- | --------------------------- |
| `RATE_LIMIT_PER_SECOND` | 1       | Maximum requests per second |
| `RATE_LIMIT_PER_MONTH`  | 15000   | Maximum requests per month  |

#### Logging

| Variable    | Default | Description                                   |
| ----------- | ------- | --------------------------------------------- |
| `LOG_LEVEL` | "info"  | Logging level: debug, info, warn, error, none |

### Examples

```bash
# Token-optimized for low VRAM (12GB RTX 5070)
DDG_MAX_RESULTS=3 DDG_MAX_SNIPPET_LENGTH=150 npm run start

# Full content for high-VRAM systems
DDG_MAX_RESULTS=10 DDG_MAX_SNIPPET_LENGTH=500 DDG_ENABLE_FULL_CONTENT=true npm run start

# Debug logging
LOG_LEVEL=debug npm run start
```

## Integration

### Claude Desktop

Add to your Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "duckduckgo": {
      "command": "npx",
      "args": ["-y", "@ericthered926/duckduckgo-mcp-server"]
    }
  }
}
```

### MCPO (Open WebUI)

For [MCPO](https://github.com/open-webui/mcpo) integration:

```json
{
  "mcpServers": {
    "duckduckgo": {
      "command": "npx",
      "args": ["-y", "@ericthered926/duckduckgo-mcp-server"],
      "env": {
        "DDG_MAX_RESULTS": "3",
        "DDG_MAX_SNIPPET_LENGTH": "150",
        "DDG_ENABLE_FULL_CONTENT": "false"
      }
    }
  }
}
```

### Local Development

```json
{
  "mcpServers": {
    "duckduckgo": {
      "command": "node",
      "args": ["/path/to/duckduckgo-mcp-server/build/index.js"],
      "env": {
        "LOG_LEVEL": "debug"
      }
    }
  }
}
```

## Development

### Scripts

| Command             | Description                   |
| ------------------- | ----------------------------- |
| `npm run build`     | Compile TypeScript            |
| `npm run start`     | Run the server                |
| `npm run dev`       | Watch mode for development    |
| `npm run lint`      | Run ESLint + Prettier check   |
| `npm run lint:fix`  | Auto-fix lint issues          |
| `npm run format`    | Format code with Prettier     |
| `npm run test`      | Run tests                     |
| `npm run typecheck` | TypeScript type checking only |

### Debugging

Use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector node build/index.js
```

### Project Structure

```
duckduckgo-mcp-server/
├── src/
│   └── index.ts          # Main server (web + news search)
├── test/
│   └── server.test.js    # Smoke tests
├── build/                 # Compiled output
├── .husky/               # Pre-commit hooks
├── eslint.config.js      # ESLint 9.x flat config
├── tsconfig.json         # Strict TypeScript config
├── .prettierrc           # Prettier formatting
├── .editorconfig         # Editor settings
└── .nvmrc                # Node version (24)
```

## Rate Limits

Default rate limits are conservative to avoid being blocked by DuckDuckGo:

- **1 request per second** - Prevents rate limiting
- **15,000 requests per month** - Reasonable monthly cap

Adjust via environment variables if needed for your use case.

## Troubleshooting

### Server won't start

1. Check Node.js version: `node --version` (should be >= 18)
2. Rebuild: `npm run build`
3. Check for TypeScript errors in build output

### Rate limit errors

- Wait for the limit window to reset (1 second for per-second, or adjust limits)
- Check if multiple instances are sharing the same counter

### No results returned

- Try a different query or remove time filters
- Check if SafeSearch is blocking results
- DuckDuckGo may return no results for very specific queries

### Debug logging

Enable debug logs to see detailed request information:

```bash
LOG_LEVEL=debug npm run start
```

## Credits

This project is a fork of [zhsama/duckduckgo-mcp-server](https://github.com/zhsama/duckduckgo-mcp-server), originally created by [zhsama](https://github.com/zhsama).

### What's New in This Fork

- **Token optimization** - Configurable result limits & snippet truncation for low-VRAM LLMs
- **Dense output format** - Single-line results to minimize token usage
- **URL cleaning** - Strips tracking params (utm\_\*, fbclid, gclid, etc.)
- **`limit` parameter** - LLM can override defaults when more context needed
- English localization (all comments and output)
- News search tool (`duckduckgo_news_search`)
- Region/locale support for localized results
- Time range filtering
- Configurable logging via `LOG_LEVEL`
- Modern ESLint 9.x flat config
- Prettier formatting
- Husky pre-commit hooks
- Comprehensive test suite
- Strict TypeScript configuration

## License

MIT - See [LICENSE](LICENSE) for details.
