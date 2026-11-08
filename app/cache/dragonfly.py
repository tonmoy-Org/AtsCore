import os
import json
import time
import secrets
import logging
import threading
from app.config import Config

logger = logging.getLogger("atscore.cache")

try:
    import redis
except ImportError:
    redis = None

_df_pool = None
_df_pool_db1 = None
_df_client = None
_df_client_db1 = None
_df_lock = threading.Lock()
_df_down_until = 0.0

LUA_RELEASE_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def _init_clients():
    global _df_pool, _df_pool_db1, _df_client, _df_client_db1, _df_down_until
    if redis is None:
        return None, None
    now = time.time()
    if now < _df_down_until:
        return None, None

    with _df_lock:
        if _df_client is not None and _df_client_db1 is not None:
            return _df_client, _df_client_db1
        try:
            _df_pool = redis.ConnectionPool(
                host=Config.DRAGONFLY_HOST,
                port=Config.DRAGONFLY_PORT,
                db=Config.DRAGONFLY_DB,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=1.0,
                max_connections=32,
            )
            _df_pool_db1 = redis.ConnectionPool(
                host=Config.DRAGONFLY_HOST,
                port=Config.DRAGONFLY_PORT,
                db=Config.DRAGONFLY_POOL_DB,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=1.0,
                max_connections=32,
            )
            c0 = redis.Redis(connection_pool=_df_pool)
            c1 = redis.Redis(connection_pool=_df_pool_db1)
            c0.ping()
            _df_client = c0
            _df_client_db1 = c1
            logger.info("DragonflyDB clients connected successfully.")
            return _df_client, _df_client_db1
        except Exception as e:
            _df_down_until = now + 5.0
            _df_client = None
            _df_client_db1 = None
            logger.debug(f"DragonflyDB not available: {e}")
            return None, None


def get_dragonfly_client():
    c0, _ = _init_clients()
    return c0


def get_dragonfly_pool_client():
    _, c1 = _init_clients()
    return c1


def cache_get_json(key: str):
    """Retrieve and parse JSON document from DragonflyDB L1 cache."""
    client = get_dragonfly_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.debug(f"cache_get_json error for {key}: {e}")
        return None


def cache_set_json(key: str, data, ttl: int = 3600):
    """Store serialized JSON document with TTL into DragonflyDB."""
    client = get_dragonfly_client()
    if client is None:
        return False
    try:
        raw = json.dumps(data, ensure_ascii=False)
        if ttl and ttl > 0:
            client.setex(key, ttl, raw)
        else:
            client.set(key, raw)
        return True
    except Exception as e:
        logger.debug(f"cache_set_json error for {key}: {e}")
        return False


def cache_pipeline_set(entries_map: dict, ttl: int = 3600):
    """Bulk pipeline set of multiple key-value pairs in sub-millisecond time."""
    client = get_dragonfly_client()
    if client is None or not entries_map:
        return 0
    try:
        pipe = client.pipeline(transaction=False)
        count = 0
        for k, v in entries_map.items():
            payload = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            if ttl and ttl > 0:
                pipe.setex(k, ttl, payload)
            else:
                pipe.set(k, payload)
            count += 1
        pipe.execute()
        return count
    except Exception as e:
        logger.debug(f"cache_pipeline_set error: {e}")
        return 0


def cache_invalidate_prefix(prefix: str):
    """Non-blocking prefix invalidation via SCAN + UNLINK."""
    client = get_dragonfly_client()
    if client is None:
        return 0
    try:
        keys_to_delete = []
        for k in client.scan_iter(match=f"{prefix}*", count=500):
            keys_to_delete.append(k)
        if keys_to_delete:
            return client.unlink(*keys_to_delete)
        return 0
    except Exception as e:
        logger.debug(f"cache_invalidate_prefix error for {prefix}: {e}")
        return 0


def acquire_lock(lock_key: str, ttl_ms: int = 5000):
    """Acquires a distributed atomic lock using SET NX PX."""
    client = get_dragonfly_client()
    if client is None:
        return None
    token = secrets.token_hex(16)
    try:
        res = client.set(f"ats:lock:{lock_key}", token, px=ttl_ms, nx=True)
        return token if res else None
    except Exception as e:
        logger.debug(f"acquire_lock failed for {lock_key}: {e}")
        return None


def release_lock(lock_key: str, token: str):
    """Releases distributed atomic lock via Lua script."""
    client = get_dragonfly_client()
    if client is None or not token:
        return False
    try:
        res = client.eval(LUA_RELEASE_LOCK, 1, f"ats:lock:{lock_key}", token)
        return res == 1
    except Exception as e:
        logger.debug(f"release_lock failed for {lock_key}: {e}")
        return False


def get_dragonfly_telemetry():
    """Live DragonflyDB v2.0+ Proactor & Memory Telemetry."""
    t0 = time.perf_counter()
    c0 = get_dragonfly_client()
    c1 = get_dragonfly_pool_client()

    if c0 is None:
        return {
            "online": False,
            "engine": "PostgreSQL Direct Fallback",
            "dragonfly_version": "offline",
        }
    try:
        pipe = c0.pipeline(transaction=False)
        pipe.info("all")
        pipe.dbsize()
        c1_size = c1.dbsize() if c1 else 0
        info_all, db0_keys = pipe.execute()
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

        hits = int(info_all.get("keyspace_hits", 0))
        misses = int(info_all.get("keyspace_misses", 0))
        hit_rate = round((hits * 100.0) / (hits + misses), 2) if (hits + misses) > 0 else 100.0

        return {
            "online": True,
            "tier": "PREMIUM_ENTERPRISE_L1",
            "engine": "DragonflyDB High-Throughput Engine",
            "dragonfly_version": str(info_all.get("dragonfly_version", "v2.0.2")),
            "redis_wire_compat": str(info_all.get("redis_version", "7.4.0")),
            "os_arch": f"{info_all.get('os', 'Linux')} ({info_all.get('arch_bits', '64')}-bit)",
            "thread_count": int(info_all.get("thread_count", 4)),
            "uptime_seconds": int(info_all.get("uptime_in_seconds", 0)),
            "connected_clients": int(info_all.get("connected_clients", 1)),
            "used_memory_human": str(info_all.get("used_memory_human", "0B")),
            "used_memory_peak_human": str(info_all.get("used_memory_peak_human", "0B")),
            "maxmemory_human": str(info_all.get("maxmemory_human", "4.00G")),
            "total_keys_db0_cache": int(db0_keys or 0),
            "total_keys_db1_pool": int(c1_size or 0),
            "instantaneous_ops_per_sec": int(info_all.get("instantaneous_ops_per_sec", 0)),
            "keyspace_hits": hits,
            "keyspace_misses": misses,
            "cache_hit_rate_pct": hit_rate,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "online": False,
            "engine": "PostgreSQL Direct Fallback",
            "error": str(e),
            "dragonfly_version": "offline",
        }


def verify_dragonfly_pipeline(num_ops: int = 100):
    """Sub-millisecond Pipeline Throughput Benchmark."""
    c0 = get_dragonfly_client()
    if c0 is None:
        return {"ok": False, "error": "DragonflyDB client offline"}
    try:
        t0 = time.perf_counter()
        pipe = c0.pipeline(transaction=False)
        test_key = "ats:health:benchmark"
        for i in range(num_ops // 2):
            pipe.set(f"{test_key}:{i}", "benchmark_ok", ex=30)
            pipe.get(f"{test_key}:{i}")
        results = pipe.execute()
        duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        ops_sec = int((num_ops / max(duration_ms / 1000.0, 0.0001)))
        return {
            "ok": True,
            "operations_count": num_ops,
            "duration_ms": duration_ms,
            "estimated_ops_per_sec": ops_sec,
            "verified": len(results) == num_ops,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

