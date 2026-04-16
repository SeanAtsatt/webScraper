# Implementation Philosophy

This document defines the philosophical principles that guide how AI agents approach development in this codebase.

## Core Principles

### 1. Understand Before Acting

- **Read first, write second** - Never propose changes to code you haven't read
- **Context is king** - Gather sufficient context before making decisions
- **Ask when uncertain** - Clarify ambiguities rather than assuming

### 2. Minimal, Focused Changes

- **Do one thing well** - Each change should have a single purpose
- **Avoid scope creep** - Don't fix what wasn't asked to be fixed
- **Leave code better** - But only in the areas you're already changing

### 3. Test-Driven Confidence

- **Tests prove correctness** - If it's not tested, it doesn't work
- **Write tests first when possible** - TDD catches design issues early
- **Trust the test suite** - Green tests = confidence to ship

### 4. Security by Default

- **Deny by default** - Whitelist, don't blacklist
- **Validate at boundaries** - Trust nothing from outside
- **Fail securely** - Errors should not leak information

### 5. Simplicity Over Cleverness

- **Boring is beautiful** - Prefer well-understood patterns
- **Explicit over implicit** - Make behavior obvious
- **Readable over compact** - Future readers will thank you

## Decision Framework

When facing a technical decision:

1. **What's the simplest approach?**
   - Can this be done without adding dependencies?
   - Can this use existing patterns in the codebase?

2. **What could go wrong?**
   - What are the failure modes?
   - How will we know if it breaks?

3. **How will this be maintained?**
   - Will the next person understand this?
   - What happens when requirements change?

4. **Is this reversible?**
   - Can we easily undo this if it's wrong?
   - Are we creating technical debt?

## Code Quality Principles

### Readability
- Names should be self-documenting
- Complex logic should have comments explaining *why*
- Functions should be short and focused

### Maintainability
- Follow the Single Responsibility Principle
- Keep dependencies explicit
- Avoid global state

### Testability
- Design for testability from the start
- Inject dependencies
- Avoid side effects in pure logic

### Performance
- Measure before optimizing
- Optimize for the common case
- Document performance trade-offs

## Communication Principles

### With Humans
- Be concise but complete
- Show your work (what you checked, what you found)
- Flag uncertainties explicitly

### In Code
- Comments explain *why*, not *what*
- Error messages should be actionable
- Logs should tell a story

### In Documentation
- Keep it up to date or don't write it
- Examples are worth a thousand words
- Link to authoritative sources

## Anti-Patterns to Avoid

### Over-Engineering
- Adding "flexibility" that's never used
- Abstracting before you have three examples
- Building for hypothetical requirements

### Under-Engineering
- Ignoring error handling
- Skipping tests "to save time"
- Copy-pasting without understanding

### Communication Failures
- Assuming context that isn't there
- Making changes without explanation
- Not flagging risks or concerns

## The Definition of Done

A task is truly done when:

1. ✅ Code works as specified
2. ✅ Tests prove it works
3. ✅ Tests prove it doesn't break existing functionality
4. ✅ Code is readable and maintainable
5. ✅ Security considerations addressed
6. ✅ Documentation updated (if needed)
7. ✅ `./scripts/verify.sh` passes

---

*"Make it work, make it right, make it fast. In that order."* - Kent Beck
