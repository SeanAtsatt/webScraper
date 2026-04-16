# AI Context Directory

This directory contains permanent reference material for AI agents. Files here are part of the repository and provide context that doesn't change frequently.

## Purpose

The `ai_context/` directory follows the "compressed documentation index" pattern (Vercel pattern) to:
- Reduce context window usage by ~80%
- Provide quick reference material
- Store implementation philosophy and guidelines
- Hold compressed versions of external documentation

## Contents

| File | Purpose |
|------|---------|
| `README.md` | This file - explains the directory |
| `PHILOSOPHY.md` | Implementation philosophy and principles |
| `COMPRESSED_DOCS_TEMPLATE.md` | Template for creating new compressed doc indexes |
| `python-tooling.md` | Python toolchain quick reference (uv, ruff, pytest, mypy) |
| `typescript-tooling.md` | TypeScript toolchain quick reference (pnpm, eslint, vitest, tsc) |
| `claude_code_standard_structure_and_security_feb_2026.md` | Claude Code standard structure and security reference |

## Usage Guidelines

### What Belongs Here
- Implementation philosophy and principles
- Compressed documentation indexes for frameworks used
- Reference material that changes infrequently
- Patterns and conventions specific to this project

### What Doesn't Belong Here
- Temporary analysis or notes (use `ai_working/`)
- Large documentation files (link to external sources instead)
- Generated content
- Environment-specific configuration

## Adding Framework Documentation

When the project uses a framework extensively, add a compressed index:

```markdown
# framework-name.md

## Quick Reference

| Task | How |
|------|-----|
| [Common task] | [Brief solution] |

## Key Concepts
- [Concept 1]: [One-line explanation]
- [Concept 2]: [One-line explanation]

## Common Patterns
[Code snippets for frequent operations]

## Gotchas
- [Common mistake and how to avoid]

## Links
- [Official docs URL]
- [Best practices guide URL]
```

## Retrieval-Led Reasoning

AI agents should:
1. Check this directory for relevant context before starting work
2. Use the compressed indexes rather than fetching full documentation
3. Only fetch external documentation when the index doesn't cover the specific need
4. Update indexes when discovering useful patterns

## Related Directories

- `ai_working/` - Temporary workspace for current tasks (gitignored)
- `docs/` - Human-facing documentation
- `.claude/` - Claude Code-specific configuration
