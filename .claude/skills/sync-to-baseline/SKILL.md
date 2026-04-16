---
description: Push improvements from a derived project back to the baseline template. Use when you've improved the Claude Code infrastructure.
allowed-tools: Bash, Read, Glob, Write
---

# /sync-to-baseline - Sync Improvements to Baseline Template

Push improvements from a derived project back to the baseline template.

## Trigger

User invokes `/sync-to-baseline` when they've made improvements to the Claude Code infrastructure that should be shared with the baseline template.

## Prerequisites

- Upstream remote configured: `git remote add upstream https://github.com/SeanAtsatt/claudeProjectBase.git`
- Run `scripts/init-project.sh` sets this up automatically

## What Gets Synced

**Template Infrastructure (sync these):**
- `.claude/settings.json` - Hook configurations
- `.claude/hooks/*.sh` - Hook scripts
- `.claude/skills/*/SKILL.md` - Skill definitions
- `.claude/agents/*.md` - Agent definitions
- `scripts/*.sh` - Utility scripts
- `AGENTS.md` - Agent contract
- `Architecture_Guardrails.md` - Design principles
- `ai_context/PHILOSOPHY.md` - Implementation philosophy
- `mcp/` - MCP infrastructure (if improved)
- `scripts/check-functional-coverage.sh` - Functional coverage checker
- `scripts/functional-requirements.template.md` - Requirements registry template
- `docs/patterns/` - Reusable pattern documentation

**Project-Specific (don't sync):**
- `CLAUDE.md` - Project-specific config
- `docs/PRD.md`, `docs/ARCH.md` - Project docs
- `.claude/sessions/` - Session history
- `ai_working/` - Working files
- Source code, tests, etc.
- `FUNCTIONAL-REQUIREMENTS.md` - Project-specific requirements (generated from template)

## Workflow

### Phase 1: Fetch Baseline State

```bash
git fetch upstream
```

Show what's different between local and upstream for template files.

### Phase 2: Identify Changes to Sync

Compare template infrastructure files:

```bash
# Files that differ from baseline
git diff upstream/main -- \
    .claude/settings.json \
    .claude/hooks/ \
    .claude/skills/ \
    .claude/agents/ \
    scripts/*.sh \
    AGENTS.md \
    Architecture_Guardrails.md \
    ai_context/PHILOSOPHY.md \
    mcp/
```

Present a summary:
```
## Changes to Sync

### Modified
- .claude/hooks/pre-bash-validate.sh (added new blocked patterns)
- .claude/skills/test/SKILL.md (improved test workflow)

### New Files
- .claude/skills/deploy/SKILL.md (new deployment skill)

### Deleted (in your project)
- None

Would you like to create a PR to sync these changes?
```

### Phase 3: Create Sync Branch

If user confirms:

1. Clone the baseline repo to a temp directory (or use worktree)
2. Copy the changed files
3. Create a branch: `sync/from-[project-name]-YYYY-MM-DD`
4. Commit with descriptive message
5. Push and create PR

```bash
# In temp clone of baseline
git checkout -b sync/from-myproject-2026-02-04
cp /path/to/project/.claude/hooks/pre-bash-validate.sh .claude/hooks/
git add .
git commit -m "Sync improvements from [project]: [summary]"
git push origin sync/from-myproject-2026-02-04
gh pr create --title "Sync: [summary]" --body "[details]"
```

### Phase 4: Provide PR Link

```
## Sync Complete

Created PR: https://github.com/SeanAtsatt/claudeProjectBase/pull/123

Changes included:
- .claude/hooks/pre-bash-validate.sh
- .claude/skills/test/SKILL.md

Please review and merge the PR in the baseline repo.

After merge, other projects can pull the updates:
  git fetch upstream
  git merge upstream/main
```

## Alternative: Manual Sync

If you prefer manual control:

```bash
# 1. See what's different
git diff upstream/main -- .claude/ scripts/ AGENTS.md

# 2. In your baseline repo clone
cd /path/to/claudeProjectBase

# 3. Copy specific files
cp /path/to/project/.claude/hooks/new-hook.sh .claude/hooks/

# 4. Commit and push
git add .
git commit -m "Add new-hook.sh from [project]"
git push
```

## Pulling Baseline Updates

To get updates FROM the baseline TO your project:

```bash
# Fetch latest baseline
git fetch upstream

# See what's new
git log HEAD..upstream/main --oneline

# Merge (careful with conflicts)
git merge upstream/main --allow-unrelated-histories

# Or cherry-pick specific commits
git cherry-pick <commit-hash>
```

## Best Practices

1. **Sync often** - Small, frequent syncs are easier than big ones
2. **Document changes** - Clear commit messages help others understand
3. **Test first** - Verify changes work before syncing
4. **Review diffs** - Make sure you're not syncing project-specific stuff
5. **Coordinate** - If multiple projects, consider which improvements to sync
