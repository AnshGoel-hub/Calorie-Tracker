from app.core.ratelimit import MemoryCounter, RedisCounter, build_counter


def test_memory_counter_counts_and_resets(monkeypatch):
    c = MemoryCounter()
    for _ in range(3):
        c.incr("k", 60)
    assert c.count("k", 60) == 3 and c.count("other", 60) == 0
    c.reset("k")
    assert c.count("k", 60) == 0


def test_memory_counter_forgets_old_hits(monkeypatch):
    import app.core.ratelimit as rl
    now = [1000.0]
    monkeypatch.setattr(rl.time, "time", lambda: now[0])
    c = MemoryCounter()
    c.incr("k", 10)
    now[0] += 11
    assert c.count("k", 10) == 0


def test_build_counter_chooses_backend():
    assert isinstance(build_counter(""), MemoryCounter)
    assert isinstance(build_counter("redis://127.0.0.1:1/0"), RedisCounter)


def test_redis_counter_fails_open_when_redis_is_down():
    c = RedisCounter("redis://127.0.0.1:1/0")      # nothing listens on port 1
    assert c.count("k", 60) == 0
    c.incr("k", 60)
    c.reset("k")                                   # none of these raise
