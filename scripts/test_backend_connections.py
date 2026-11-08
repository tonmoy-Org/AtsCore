#!/usr/bin/env python3
"""
Test Connections Script
Tests PostgreSQL 16 connection and DragonflyDB telemetry.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import check_pg_health
from app.cache.dragonfly import get_dragonfly_telemetry, verify_dragonfly_pipeline

if __name__ == "__main__":
    print("=== Testing AtsCore Backend Infrastructure ===")
    print("\n1. Testing PostgreSQL 16 Connection...")
    pg = check_pg_health()
    if pg.get("online"):
        print(f" [OK] PostgreSQL is ONLINE! Version: {pg.get('version')[:40]}... Latency: {pg.get('latency_ms')}ms")
    else:
        print(f" [WARNING] PostgreSQL connection failed: {pg.get('error')}")

    print("\n2. Testing DragonflyDB In-Memory Cache...")
    df = get_dragonfly_telemetry()
    if df.get("online"):
        print(f" [OK] DragonflyDB is ONLINE! Version: {df.get('dragonfly_version')}, Memory: {df.get('used_memory_human')}, Latency: {df.get('latency_ms')}ms")
        print("\n3. Testing 100-Operation Pipeline Benchmark...")
        bench = verify_dragonfly_pipeline(100)
        print(f" Benchmark: {bench.get('estimated_ops_per_sec')} ops/sec ({bench.get('duration_ms')}ms for 100 ops)")
    else:
        print(f" [WARNING] DragonflyDB offline: {df.get('engine')}")

