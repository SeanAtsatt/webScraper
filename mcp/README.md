# MCP (Model Context Protocol) via Docker MCP Gateway

This directory contains documentation for the project's MCP server infrastructure. All MCP servers are managed by the **Docker MCP Gateway** -- a single entry point that provides access to 270+ pre-built, signed servers from the Docker MCP Catalog.

## Overview

MCP servers extend Claude Code with external capabilities (GitHub APIs, databases, web search, documentation lookup, etc.). Instead of manually building and managing Docker containers for each server, the Docker MCP Gateway:

- **Manages container lifecycle automatically** -- containers start on-demand when a tool is called, not upfront
- **Provides security isolation** -- each server runs in its own container with resource limits, no host filesystem access, and image signature verification
- **Offers 270+ curated servers** from the Docker MCP Catalog, ready to use without custom Dockerfiles
- **Injects secrets securely** via Docker's secret store integration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                             │
└─────────────────┬───────────────────────────────────────────┘
                  │ MCP Protocol (single connection)
┌─────────────────▼───────────────────────────────────────────┐
│              Docker MCP Gateway                              │
│         (manages all MCP servers)                            │
│                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  context7   │ │   brave     │ │  postgres   │  ...      │
│  │ (on-demand) │ │ (on-demand) │ │ (on-demand) │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │               │               │                    │
│  Docker containers started lazily when tools are called      │
└─────────────────────────────────────────────────────────────┘
```

## Server Selection: Two Modes

### 1. Static Baseline (`.docker-mcp.yaml`)

Version-controlled file in the project root listing servers this project always needs. Checked into the repo so all team members get the same MCP capabilities.

```yaml
# .docker-mcp.yaml
servers:
  - context7    # Documentation lookup (always useful)
```

### 2. Dynamic Discovery (`mcp-find` / `mcp-add`)

During a session, Claude can search the Docker MCP Catalog for servers by keyword, enable them on-the-fly, and configure them -- without editing any files.

**Example:** If a task requires web search and `brave` isn't in the baseline, Claude can:
1. `mcp-find` for "web search"
2. `mcp-add` the brave server
3. Use it immediately
4. `mcp-remove` when done (to reclaim context)

**Gateway discovery tools:**

| Tool | Purpose |
|------|---------|
| `mcp-find` | Search the Docker MCP Catalog by keyword |
| `mcp-add` | Enable a server for this session |
| `mcp-config-set` | Configure secrets or parameters for a server |
| `mcp-remove` | Disable a server (reclaims context window space) |
| `mcp-exec` | Execute a tool from a specific server |

### When to Use Which Mode

| Mode | Best For | Examples |
|------|----------|---------|
| **Static** (`.docker-mcp.yaml`) | Servers needed every session | `context7` for docs |
| **Dynamic** (`mcp-add`) | Situational needs | `brave` for web research, `playwright` for browser testing, `mongodb` for a Mongo project |

## Context Management

Every loaded MCP server adds tool definitions (name, description, parameter schemas) to Claude's context window. More servers = more context consumed = less room for conversation and code.

### Best Practices

- **Keep `.docker-mcp.yaml` minimal** -- only servers needed in every session
- **Use dynamic loading** (`mcp-add`) for situational servers, and unload them (`mcp-remove`) when the task is done
- **Use `/mcp-manage`** to see what's currently loaded and its context impact

### Typical Context Costs

Each server contributes ~200-500 tokens of tool definitions depending on how many tools it exposes. A baseline of 2-3 servers is cheap; loading 10+ simultaneously is expensive.

The gateway's `mcp-add` has an `activate` parameter -- setting `activate: false` registers a server without loading its tools into context until explicitly needed.

## Recommended Servers by Use Case

The Docker MCP Catalog has 312+ servers. Here are high-value picks organized by workflow. All can be loaded dynamically -- ask Claude to `mcp-find` and `mcp-add` as needed.

| Use Case | Server | What It Adds | Config Needed? |
|----------|--------|--------------|----------------|
| **Always On** | `context7` | Library docs lookup | No |
| **GitHub workflow** | `github` | PRs, issues, repo ops | OAuth |
| **Web research** | `brave` | Web search | API key |
| **Web fetching** | `fetch` | Fetch URL as markdown | No |
| **Database** | `postgres` / `mongodb` / `redis` | DB queries | Connection string |
| **Browser testing** | `playwright` | Browser automation | No |
| **Issue tracking** | `linear` / `asana` | Issue CRUD | OAuth/API key |
| **Messaging** | `slack` | Channel messages | OAuth |
| **Cloud ops** | `aws` / `gcp` / `azure` | Cloud resource mgmt | Credentials |
| **Code search** | `ast-grep` | Structural code search | No |
| **Docs hosting** | `deepwiki` / `atlas-docs` | Documentation retrieval | No |
| **File conversion** | `markitdown` / `markdownify` | Convert files to markdown | No |

**To browse the full catalog:**
- In a session: ask Claude to `mcp-find "keyword"`
- From terminal: `docker mcp catalog show docker-mcp`
- Online: [Docker MCP Catalog](https://hub.docker.com/extensions/docker/labs-mcp-gateway)

**Configuring secrets** (for servers that need OAuth/API keys):
```bash
# Via Claude in-session:
# Ask Claude to use mcp-config-set with the server name and config

# Via Docker CLI:
docker mcp server inspect <name>   # See required config schema
```

## Setup

### Prerequisites

1. **Docker Desktop 4.59+** with MCP Toolkit enabled
   - Open Docker Desktop > Settings > Features > Enable "MCP Toolkit"
2. **Docker MCP CLI** available (`docker mcp` commands)

### Configuration

**`.docker-mcp.yaml`** (project root) -- defines the static baseline:

```yaml
servers:
  - context7
```

**`.mcp.json`** (project root) -- connects Claude Code to the gateway:

```json
{
  "mcpServers": {
    "docker-mcp-gateway": {
      "command": "docker",
      "args": ["mcp", "gateway", "run", "--config", ".docker-mcp.yaml"]
    }
  }
}
```

### Verify Setup

```bash
# Check gateway CLI is available
docker mcp server ls

# Run project healthcheck
./scripts/mcp_healthcheck.sh
```

## Security Model

The Docker MCP Gateway provides built-in security isolation:

| Constraint | Details |
|------------|---------|
| **Resource limits** | 1 CPU / 2GB memory per server container |
| **Filesystem** | No host filesystem access |
| **Image verification** | Signed images from Docker MCP Catalog |
| **Secret management** | Docker secret store integration (not env files) |
| **Network** | Configurable with `--block-network` flag |

Additional security flags:
- `--block-network` -- block all network access for a server
- `--verify-signatures` -- enforce image signature verification
- `--block-secrets` -- prevent secret injection

## Available Servers

Browse the full catalog: [Docker Hub MCP Catalog](https://hub.docker.com/extensions/docker/labs-mcp-gateway)

**Common categories:**

| Category | Examples |
|----------|---------|
| **Dev Tools** | `context7` (docs), `github`, `gitlab` |
| **Databases** | `postgres`, `mongodb`, `redis`, `sqlite` |
| **Search** | `brave`, `exa`, `tavily` |
| **Cloud** | `aws`, `gcp`, `azure` |
| **Productivity** | `slack`, `linear`, `notion` |
| **Testing** | `playwright`, `puppeteer` |

## CLI Reference

```bash
# List enabled servers
docker mcp server ls

# Enable/disable a server
docker mcp server enable <name>
docker mcp server disable <name>

# Run the gateway
docker mcp gateway run --config .docker-mcp.yaml

# Validate configuration
docker mcp gateway run --dry-run --config .docker-mcp.yaml

# Read/write gateway config
docker mcp config read
docker mcp config write
```

## Testing

MCP configuration and dynamic loading are tested in two layers:

| Layer | File | What it Tests | Cost |
|-------|------|---------------|------|
| Infrastructure | `tests/mcp/gateway.bats` | Static config, healthcheck, cleanup | Free |
| Infrastructure | `tests/mcp/dynamic-loading.bats` | Enable/disable lifecycle, context measurement, robustness | Free |
| E2E | `tests/mcp/e2e-dynamic-loading.bats` | Claude-driven mcp-find/add/remove via `claude -p` | ~$0.50 max |

```bash
# Run all MCP tests (Layer 1 only)
./scripts/run-tests.sh mcp

# Run including E2E (requires Claude CLI + API key)
CLAUDE_E2E=1 ./scripts/run-tests.sh mcp
```

Tests skip gracefully when Docker MCP Gateway or Claude CLI is unavailable.

## References

- [Docker MCP Gateway Documentation](https://docs.docker.com/ai/mcp-catalog-and-toolkit/)
- [Docker MCP Catalog](https://hub.docker.com/extensions/docker/labs-mcp-gateway)
- [Docker MCP Gateway GitHub](https://github.com/docker/labs-mcp-gateway)
- [Model Context Protocol](https://modelcontextprotocol.io/)
