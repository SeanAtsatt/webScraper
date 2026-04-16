# Claude Code Project “Standard Structure” + MCP-in-Docker Security Gates (Feb 2026)

This document captures a **modern, widely-used** project structure and workflow patterns for **new Claude Code projects**, including:

- **Task lists** and a “definition of done” (DoD) that is test-validated
- **Parallelization** using worktrees and subagents
- **Skills + agents management**, including support for **AGENTS.md**
- **MCP** usage with a strong preference for **Docker isolation**
- A **security gating** approach: “anything executable is untrusted until proven otherwise”
- **Example repositories/templates** that demonstrate these patterns

---

## 1) Repo scaffold (Claude Code-first)

A practical “standard” scaffold looks like this:

```text
repo/
  AGENTS.md                # portable agent contract (works across tools)
  CLAUDE.md                # Claude Code project memory + pointers (includes @AGENTS.md)

  docs/
    PRD.md                 # scope + acceptance criteria
    ARCH.md                # architecture + boundaries
    TEST-STRATEGY.md       # what proves “done”
    ADR/                   # decisions (small + dated)

  .claude/
    settings.json          # project-level permissions + hooks (checked in)
    settings.local.json    # local overrides (not checked in)
    skills/                # reusable slash workflows
      startup/SKILL.md
      session-save/SKILL.md
      test/SKILL.md
      review/SKILL.md
      security/SKILL.md
      mcp-manage/SKILL.md
    agents/                # subagents / specialists
      explorer.md
      implementer.md
      tester.md
      security-auditor.md

  .mcp.json                # project MCP config (checked in, points to Docker MCP Gateway)
  .docker-mcp.yaml         # static baseline of MCP servers from Docker MCP Catalog
  mcp/
    README.md              # MCP setup, security model, context management

  scripts/
    verify.sh              # single “definition-of-done” entrypoint
    security_gate.sh       # scans + allowlist checks
    mcp_healthcheck.sh     # prove MCP servers are up & constrained
```

**Key idea:** keep the root “contract” thin (AGENTS.md + CLAUDE.md), and place operational details in `.claude/`, `scripts/`, and `mcp/`.

---

## 2) Task lists + a test-driven Definition of Done (DoD)

### 2.1 Task lists as the controller

A reliable “Claude Code style” task has:

1. **Deliverable**: what changes (files, behavior)
2. **Acceptance checks**: tests + lint + type checks + security checks
3. **Evidence**: command output or CI artifact
4. **Rollback note**: what to revert if needed

### 2.2 “Done” == `scripts/verify.sh` is green

Make `verify.sh` the single entrypoint for “definition of done”.

Typical `verify.sh` components:
- unit tests
- integration tests (if present)
- lint/format
- typecheck
- dependency audit
- secret scan
- container scan (if Docker/MCP involved)

Then enforce a policy:
- **No task is complete until `verify.sh` passes locally** (or via CI if it’s too heavy for local).

---

## 3) Parallelization that works in practice

### 3.1 Worktrees: the most stable approach to true concurrency

Use git worktrees for parallel Claude sessions:

- one worktree = one feature branch = one Claude session
- merge only after `verify.sh` + CI are green

This avoids context collisions and makes rollback trivial.

### 3.2 Subagents + background tasks (inside a session)

Use subagents for specialization and short-lived, bounded work:
- `explorer` (mapping / read-only)
- `implementer` (small edits + quick tests)
- `tester` (tests-first or regression coverage)
- `security-auditor` (treats exec as hostile by default)

Use backgrounding for long-running checks (build/test).  
Operational note: keep **MCP-dependent work** in the main agent/foreground paths; treat MCP tools as “not guaranteed” in background subagents, depending on your configuration and tool limitations.

---

## 4) Skills + agents management (including AGENTS.md)

### 4.1 AGENTS.md (portable contract)

Use **AGENTS.md** as your cross-tool standard:
- invariants (“never do X”)
- DoD definition
- allowed / disallowed tool actions
- parallelism rules (worktrees vs subagents)
- MCP policy (Docker-only; allowlist egress; no host exec)

### 4.2 CLAUDE.md (Claude Code-specific pointers)

Keep **CLAUDE.md** short:
- point to AGENTS.md
- list “how to run verify”
- point to docs/ for deep context
- list common commands (optional)

### 4.3 Skills: the minimal set that scales

A practical minimum skill set:

- `/startup` → session initialization with context loading
- `/session-save` → save session summary for next session
- `/test` → runs fastest tests first, then expands
- `/review` → code review checklist + dependency sanity
- `/security` → runs security gate + summarizes failures
- `/mcp-manage` → MCP server visibility and context management

Generic skills live in `~/.claude/skills/` (installed via `install-global.sh`). Only project-specific skills go in `.claude/skills/`.

---

## 5) MCP: Docker MCP Gateway + "everything executable is untrusted" validation

The standard is:
- **MCP servers run via the Docker MCP Gateway** (270+ curated, signed servers from the Docker MCP Catalog)
- **Deny-by-default execution on the host**
- **Treat all executables and scripts as untrusted unless allowlisted**

The Docker MCP Gateway replaces manual docker-compose setups. It manages container lifecycle, security isolation, and secret injection automatically. Servers start on-demand (lazily) when a tool is called.

**Two modes of server selection:**
- **Static baseline** (`.docker-mcp.yaml`): Version-controlled file listing servers always available. Checked into repo.
- **Dynamic discovery** (`mcp-find` / `mcp-add`): Search the Docker MCP Catalog during a session, enable servers on-the-fly, unload with `mcp-remove` when done.

### 5.1 Gateway-provided constraints (built-in)

The Docker MCP Gateway enforces these automatically for all servers:
- Container isolation with resource limits (1 CPU / 2GB per server)
- No host filesystem access
- Signed image verification from Docker MCP Catalog
- Docker secret store integration (not env files or committed credentials)
- Configurable network restrictions (`--block-network`, `--verify-signatures`, `--block-secrets`)
- Custom/untrusted MCP servers require explicit security review before use

### 5.2 Security gates: hooks + allowlists + CI mirroring

A common “secure-by-default” pattern:

1) **Pre-exec gate (hook)** for shell execution:
   - deny by default
   - allowlist command prefixes
   - block obvious fetch/execution (`curl|wget|bash -c …`) unless explicitly approved
   - require “run inside container” for third-party code execution

2) **Post-edit gate**:
   - run the narrowest test/lint/typecheck required for the touched area

3) **CI gate mirrors local gate**:
   - runs `scripts/verify.sh`
   - runs container image scans for MCP images

### 5.3 “Executable inventory” policy

Add a repository policy (in AGENTS.md) that:
- enumerates “approved executables” (scripts you allow)
- requires new scripts/executables to be reviewed and added to an allowlist
- requires new dependencies to pass audit + lockfile update + provenance checks

---

## 6) Repositories/templates showing “standard structure”

Below are examples that demonstrate all or parts of the above structure.

### 6.1 “Structure-complete” example repos (good to copy)

- **ChrisWiles/claude-code-showcase**  
  Modern Claude Code project config: CLAUDE.md, `.claude/settings.json`, agents/commands, plus MCP config.  
  https://github.com/ChrisWiles/claude-code-showcase

- **bkrabach/ai-code-project-template**  
  Template repo including `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.mcp.json`, and workflow structure.  
  https://github.com/bkrabach/ai-code-project-template

- **AndrewAltimit/template-repo**  
  Template calling out `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, and Docker-compose as first-class.  
  https://github.com/AndrewAltimit/template-repo

### 6.2 Template installers / catalogs

- **davila7/claude-code-templates**  
  CLI + catalog of agents, commands, settings, hooks, MCP integrations.  
  https://github.com/davila7/claude-code-templates

- **SuperClaude-Org/SuperClaude_Framework**  
  A heavier “framework” reference for commands/personas/methodologies.  
  https://github.com/SuperClaude-Org/SuperClaude_Framework

### 6.3 Skills / commands / agent collections

- **anthropics/skills** (official)  
  https://github.com/anthropics/skills

- **wshobson/agents** and **wshobson/commands** (popular)  
  https://github.com/wshobson/agents  
  https://github.com/wshobson/commands

- **hesreallyhim/awesome-claude-code** (index / directory)  
  https://github.com/hesreallyhim/awesome-claude-code

### 6.4 MCP reference

- **Docker MCP Gateway** (recommended approach for all MCP servers)
  https://github.com/docker/labs-mcp-gateway

- **Docker MCP Catalog** (270+ curated, signed servers)
  https://hub.docker.com/extensions/docker/labs-mcp-gateway

- **Docker MCP Documentation**
  https://docs.docker.com/ai/mcp-catalog-and-toolkit/

- **modelcontextprotocol/servers** (canonical reference implementations)
  https://github.com/modelcontextprotocol/servers

---

## 7) How to evaluate whether a repo matches “your standard”

When you inspect a candidate template, check:

**Structure**
- Has AGENTS.md + CLAUDE.md (or an equivalent contract + tool-specific pointers)?
- Has `.claude/settings.json` (not just ad-hoc instructions)?
- Has `.mcp.json` and `.docker-mcp.yaml` for MCP via Docker MCP Gateway?

**Validation**
- Is there a single `verify.sh` or CI entry that proves “done”?
- Are tests present and required?
- Are lint/type checks enforced?

**Security**
- Is there a deny-by-default policy for executing commands?
- Are scripts allowlisted?
- Are MCP servers managed via Docker MCP Gateway with signed catalog images?

**Concurrency**
- Does it recommend worktrees or a stable parallel model?
- Does it define subagents with bounded roles?

---

## 8) Next step: generate your exact starter kit

If you tell me:
- language/runtime (Node/Python/Go/Rust/etc.)
- test runner (pytest/jest/vitest/go test/etc.)
- CI (GitHub Actions/etc.)
- package manager (pnpm/uv/poetry/etc.)

…I can generate a **complete repo skeleton** (Markdown + configs + scripts) that:
- enforces “everything executable is untrusted” by default
- runs MCP servers in Docker
- has a strict `verify.sh` definition-of-done gate
- supports parallelization and skills/agents from day one

---

**Generated:** 2026-02-04
