# Architecture Guardrails & Checklist

This document should be placed at the **front of any architecture design doc**.  
It enforces robust, reliable solutions by requiring an *architecture-first* approach before code is written.

---

## Design Guardrails (MUST)
- State assumptions & unknowns; propose fast validations.
- Prefer simple, boring tech unless justified with trade-offs.
- Idempotency, timeouts, retries (jitter), and circuit breakers where relevant.
- Twelve-factor config; secrets out of code; PII redaction in logs.
- Observability: metrics, logs, traces; health checks; basic SLOs.

---

## Architecture Pass (before coding)
1. Propose 2–3 options (diagram + data flow).
2. Compare trade-offs (complexity, cost, risk, ops).
3. Choose one; justify against NFRs (perf, security, reliability, maintainability).
4. Detail interfaces, data model, error boundaries, concurrency, caching.
5. Failure modes (top 10) + mitigations.
6. Testing plan (unit/contract/integration/e2e) and observability plan.
7. Incremental delivery (MVP → v1) and rollback plan.

---

## Skeptical Review (self-critique)
- 5 realistic prod failure modes → patches.
- What’s over-engineered? Apply YAGNI.
- Cut 30% scope for 80% value—what goes?
- Single success metric + how to measure.

---

## Acceptance Checklist (ALL must be true)
- [ ] Option matrix + chosen design rationale present.
- [ ] Interfaces/types defined before code.
- [ ] Perf/security budgets stated (e.g., p95 latency, leak surface).
- [ ] Test plan + sample alerts included.
- [ ] ADR summary written (why this design now).

---

## Anti-Goals / Forbidden
- ❌ Hidden global state, mixed concerns, env-coupled code.
- ❌ Long-running requests without timeouts; blind retries; non-idempotent writes.
- ❌ Storing secrets in repo; logging raw PII.

---

## Machine-Readable Policy (optional)
```json
{
  "nfr": ["reliability","security","performance","maintainability","privacy","observability"],
  "must": ["architecture_pass","skeptical_review","acceptance_checklist"],
  "forbidden": ["global_state","no_timeouts","pii_in_logs","secrets_in_code"]
}
```

---

## Prompt to Pair with This Doc
> “**Follow the document’s Guardrails and Architecture Pass.** If a direct approach is fragile or impossible, **reframe** and offer alternatives. **Do not write full code** until the acceptance checklist is satisfied and an ADR is produced.”
