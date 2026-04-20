# Installer guide (for the technical helper)

This walks through setting up `webscraper-mcp` for a non-technical end user on a blank macOS machine.

## Before you start

- You need keyboard access to the target machine for ~10-15 minutes.
- The user should know their computer password (for any `sudo` prompts that come up, though we avoid those where possible).
- Claude Desktop is a separate install from Anthropic; you'll download it mid-way through.

## Steps

1. Open https://github.com/SeanAtsatt/webScraper in Safari.
2. Click **Code → Download ZIP**.
3. Open the downloaded ZIP in Finder (macOS auto-unzips it).
4. Open Terminal and `cd` to the extracted folder:
   ```
   cd ~/Downloads/webScraper-main
   ```
5. Run the installer:
   ```
   ./scripts/install-mcp.sh
   ```
6. Answer each prompt with `Y` (or just press Enter).
7. When the script tells you to install Claude Desktop, download from https://claude.ai/download, install it, then re-run `./scripts/install-mcp.sh`.
8. Re-launch Claude Desktop after the installer finishes.

## Verifying it works

Open Claude Desktop. Start a new conversation. Say:

> "Please check the webscraper environment."

Claude should use the `check_environment` tool and report any issues.

## Troubleshooting

- **"uv not found" after install** — close and re-open Terminal; the installer-added PATH needs a fresh shell.
- **Playwright download times out** — re-run the installer; it's idempotent.
- **Claude Desktop shows no tools** — check `~/Library/Application Support/Claude/claude_desktop_config.json` has a `webscraper` entry; restart Claude Desktop.
- **Full install log** — `~/.webscraper/install.log`.

## Uninstall

```
./scripts/install-mcp.sh --uninstall
```

Removes the MCP entry from Claude Desktop's config. Leaves the extracted folder and auth data alone (delete those manually if you want a full cleanup).
