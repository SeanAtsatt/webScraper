"""Tier dispatcher with escalation rule."""

from __future__ import annotations

from dataclasses import dataclass

from webscraper.challenge import is_challenge_page
from webscraper.envelope import FetchResult, TierAttempt, TierName
from webscraper.errors import AllTiersFailedError, FetcherError
from webscraper.fetch.base import Fetcher, FetcherResult, FetchOptions
from webscraper.log import get_logger
from webscraper.parse import parse_to_envelope

_log = get_logger("dispatcher")


@dataclass(frozen=True)
class DispatchOptions:
    auto_escalate: bool = True
    forced_tier: TierName | None = None
    min_content_chars: int = 200
    fetch_opts: FetchOptions = FetchOptions()


class Dispatcher:
    def __init__(self, fetchers: list[Fetcher]) -> None:
        self._fetchers = fetchers

    def run(self, url: str, opts: DispatchOptions) -> FetchResult:
        chain = self._build_chain(opts)
        history: list[TierAttempt] = []

        for fetcher in chain:
            _log.info("tier_attempt_start", extra={"tier": fetcher.name, "url": url})
            try:
                fr = fetcher.fetch(url, opts.fetch_opts)
            except FetcherError as exc:
                history.append(
                    TierAttempt(
                        tier=fetcher.name,
                        outcome="escalated",
                        elapsed_ms=0,
                        reason=exc.reason,
                    )
                )
                continue

            tmp_history = history + [
                TierAttempt(
                    tier=fetcher.name,
                    outcome="success",
                    elapsed_ms=fr.elapsed_ms,
                )
            ]
            envelope = parse_to_envelope(
                fr,
                requested_url=url,
                tier_history=tmp_history,
            )

            reason = self._unacceptable_reason(fr, envelope, opts.min_content_chars)
            if reason is None:
                history.append(tmp_history[-1])
                return envelope.model_copy(
                    update={
                        "meta": envelope.meta.model_copy(
                            update={"tier_history": history, "tier_used": fetcher.name}
                        )
                    }
                )

            history.append(
                TierAttempt(
                    tier=fetcher.name,
                    outcome="escalated",
                    elapsed_ms=fr.elapsed_ms,
                    reason=reason,
                )
            )

        raise AllTiersFailedError(f"all tiers failed: {[t.reason or t.outcome for t in history]}")

    def _build_chain(self, opts: DispatchOptions) -> list[Fetcher]:
        if opts.forced_tier is not None:
            return [f for f in self._fetchers if f.name == opts.forced_tier]
        if not opts.auto_escalate:
            return self._fetchers[:1]
        return list(self._fetchers)

    @staticmethod
    def _unacceptable_reason(
        fr: FetcherResult, envelope: FetchResult, min_chars: int
    ) -> str | None:
        if not (200 <= fr.http_status < 300):
            return f"http_{fr.http_status}"
        detected, reason = is_challenge_page(fr.html)
        if detected:
            return reason
        if len(envelope.markdown) < min_chars:
            return "insufficient_content"
        return None
