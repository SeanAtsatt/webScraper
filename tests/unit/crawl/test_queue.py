"""URL normalization + CrawlQueue tests."""

import asyncio

from webscraper.crawl.queue import CrawlQueue, normalize_url


# [F-REQ-029]
def test_normalize_drops_fragment() -> None:
    assert normalize_url("https://ex.com/p#section") == "https://ex.com/p"


# [F-REQ-029]
def test_normalize_strips_tracking_params() -> None:
    out = normalize_url("https://ex.com/p?utm_source=x&utm_medium=y&real=1&fbclid=abc")
    assert out == "https://ex.com/p?real=1"


# [F-REQ-029]
def test_normalize_sorts_query_params() -> None:
    out = normalize_url("https://ex.com/p?b=2&a=1&c=3")
    assert out == "https://ex.com/p?a=1&b=2&c=3"


# [F-REQ-029]
def test_normalize_lowercases_scheme_and_host() -> None:
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


# [F-REQ-029]
def test_normalize_preserves_path_case() -> None:
    assert normalize_url("https://ex.com/CaSe") == "https://ex.com/CaSe"


# [F-REQ-029]
def test_queue_enqueue_deduplicates_normalized_urls() -> None:
    async def go() -> tuple[bool, bool]:
        q = CrawlQueue(max_pages=10)
        first = await q.enqueue("https://ex.com/p?a=1&b=2", depth=0, discovered_from=None)
        second = await q.enqueue("https://ex.com/p?b=2&a=1#frag", depth=0, discovered_from=None)
        return first, second

    first, second = asyncio.run(go())
    assert first is True
    assert second is False


# [F-REQ-025]
def test_queue_respects_max_pages() -> None:
    async def go() -> tuple[bool, bool, bool]:
        q = CrawlQueue(max_pages=2)
        r1 = await q.enqueue("https://ex.com/1", depth=0, discovered_from=None)
        r2 = await q.enqueue("https://ex.com/2", depth=0, discovered_from=None)
        r3 = await q.enqueue("https://ex.com/3", depth=0, discovered_from=None)
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(go())
    assert r1 is True
    assert r2 is True
    assert r3 is False


# [F-NONE]
def test_queue_pop_returns_enqueued_items() -> None:
    async def go() -> list[tuple[str, int, str | None]]:
        q = CrawlQueue(max_pages=10)
        await q.enqueue("https://ex.com/1", depth=0, discovered_from=None)
        await q.enqueue("https://ex.com/2", depth=1, discovered_from="https://ex.com/1")
        q.close_for(1)
        out = []
        while (item := await q.pop()) is not None:
            out.append(item)
        return out

    items = asyncio.run(go())
    assert items[0] == ("https://ex.com/1", 0, None)
    assert items[1] == ("https://ex.com/2", 1, "https://ex.com/1")


# [F-NONE]
def test_queue_visited_count_tracks_enqueues() -> None:
    async def go() -> int:
        q = CrawlQueue(max_pages=10)
        await q.enqueue("https://ex.com/1", 0, None)
        await q.enqueue("https://ex.com/2", 0, None)
        await q.enqueue("https://ex.com/1", 0, None)  # dup, shouldn't count
        return q.visited_count

    assert asyncio.run(go()) == 2


# [F-NONE]
def test_queue_mark_done_tracks_in_flight() -> None:
    async def go() -> tuple[bool, bool, bool]:
        q = CrawlQueue(max_pages=10)
        await q.enqueue("https://ex.com/1", 0, None)
        a = q.is_drained()  # queue not empty → not drained
        _ = await q.pop()
        b = q.is_drained()  # queue empty but in-flight=1 → not drained
        q.mark_done()
        c = q.is_drained()  # empty AND in-flight=0 → drained
        return a, b, c

    a, b, c = asyncio.run(go())
    assert (a, b, c) == (False, False, True)
