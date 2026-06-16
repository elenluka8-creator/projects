# MCP Tool Configuration

This document describes MCP (Model Context Protocol) tool servers that can be used with agent-system tool-agents.

---

## Overview

Tool-agents (currently: Illustrator) require external MCP tool servers to be configured in `.cursor/mcp.json`. Without the required MCP server, tool-agents return `status: "blocked"` and cannot proceed.

---

## Illustrator agent (image generation)

The Illustrator agent requires an MCP image generation server.

### Supported tools

| MCP server | Provider | Notes |
|---|---|---|
| `nanobanana-mcp` | Google Imagen / Nano Banana 2 | Recommended |
| `mcp-image` | Nano Banana 2 | Auto-prompt optimization |
| Any server exposing `image_generate` | — | Must accept subject, style, aspect_ratio parameters |

### Setup

1. Install the MCP server package (see provider docs)
2. Add the server configuration to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "nanobanana-mcp": {
      "command": "npx",
      "args": ["-y", "nanobanana-mcp"],
      "env": {
        "GOOGLE_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

3. Restart Cursor to load the new MCP configuration
4. Verify by asking the Illustrator agent to generate a test image

### Without MCP

If no image generation MCP server is configured, Illustrator returns:

```
status: "blocked"
blocked_reason: "No image generation MCP tool configured"
```

In this case, Designer or Marketing agents will need to source images manually or describe visual requirements in briefs without generating assets.

---

## Adding new MCP tools

When a new MCP tool is needed for a tool-agent:

1. Add a section to this document describing the tool and its setup
2. Update the relevant agent file (`agents/<agent>.md`) to reference this document
3. Record the decision to add the tool in `docs/DECISIONS.md` if it affects architecture
