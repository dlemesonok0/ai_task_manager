"""
Профилирование ресурсов backend-приложения.

Использование:
    uv run python profile.py              # полный отчёт
    uv run python profile.py imports      # только импорты
    uv run python profile.py memory       # только память
    uv run python profile.py cpu          # только CPU
    uv run python profile.py endpoints    # только эндпоинты
    uv run python profile.py system       # только система
    uv run python profile.py docker       # Docker-контейнеры
    uv run python profile.py frontend     # Фронтенд билд
    uv run python profile.py all          # полный отчёт (как без аргументов)
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import tracemalloc

import psutil

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:15432/ai_task_manager")

proc = psutil.Process(os.getpid())


def mb(n: int | float) -> float:
    return n / 1024 / 1024


def sep(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── System ──────────────────────────────────────────────────────────────────

def profile_system():
    sep("SYSTEM")
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    total_ram = psutil.virtual_memory().total / 1024 / 1024 / 1024

    print(f"CPU cores:            {cpu_count}")
    if cpu_freq:
        print(f"CPU freq:             {cpu_freq.current:.0f} MHz")
    print(f"Total RAM:            {total_ram:.1f} GB")
    print(f"Process CPU%:         {proc.cpu_percent(interval=1):.1f}%")
    print(f"Process threads:      {proc.num_threads()}")
    print(f"Process open files:   {len(proc.open_files())}")
    print(f"Process connections:  {len(proc.net_connections())}")


# ── Imports (пошаговый) ────────────────────────────────────────────────────

def profile_imports():
    sep("IMPORTS (пошаговый замер памяти)")

    snapshots: list[tuple[str, float, int]] = []

    def snap(label: str):
        mi = proc.memory_info()
        rss = mb(mi.rss)
        threads = proc.num_threads()
        snapshots.append((label, rss, threads))
        prev_rss = snapshots[-2][1] if len(snapshots) > 1 else 0
        delta = rss - prev_rss if len(snapshots) > 1 else 0
        sign = "+" if delta >= 0 else ""
        print(f"  {label:25s} RSS={rss:7.1f} MB  ({sign}{delta:.1f})  threads={threads}")

    print(f"  {'module':25s} {'RSS':>10s} {'delta':>10s}")
    print(f"  {'-' * 25} {'-' * 10} {'-' * 10}")

    snap("baseline")

    t0 = time.perf_counter()
    from fastapi import FastAPI  # noqa: F401
    print(f"  {'fastapi':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("fastapi")

    t0 = time.perf_counter()
    from services.auth_service import create_access_token  # noqa: F401
    print(f"  {'auth_service':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("auth_service")

    t0 = time.perf_counter()
    from services import db_service  # noqa: F401
    print(f"  {'db_service':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("db_service")

    t0 = time.perf_counter()
    from services.ai_service import ai_service  # noqa: F401
    print(f"  {'ai_service':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("ai_service")

    t0 = time.perf_counter()
    from services.todoist_service import todoist_service_for_token  # noqa: F401
    print(f"  {'todoist_service':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("todoist_service")

    t0 = time.perf_counter()
    from services.gcal_service import gcal_service_for_token  # noqa: F401
    print(f"  {'gcal_service':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("gcal_service")

    t0 = time.perf_counter()
    from main import app  # noqa: F401
    print(f"  {'main (full)':25s} {(time.perf_counter() - t0) * 1000:6.0f}ms")
    snap("main (full)")

    print(f"\n  Итого: {snapshots[-1][1]:.1f} MB RSS")

    # Топ по потреблению
    deltas = []
    for i in range(1, len(snapshots)):
        name, rss, _ = snapshots[i]
        prev_rss = snapshots[i - 1][1]
        deltas.append((name, rss - prev_rss))
    deltas.sort(key=lambda x: x[1], reverse=True)

    print(f"\n  Топ модулей по потреблению памяти:")
    for name, delta in deltas:
        bar = "#" * int(delta / 2)
        print(f"    {name:25s} {delta:+6.1f} MB  {bar}")


# ── Memory ─────────────────────────────────────────────────────────────────

def profile_memory():
    sep("MEMORY (tracemalloc)")

    mem_before = proc.memory_info()
    print(f"RSS до импорта:       {mb(mem_before.rss):.1f} MB")
    print(f"VMS до импорта:       {mb(mem_before.vms):.1f} MB")

    tracemalloc.start()

    from main import app  # noqa: F401
    from services import db_service  # noqa: F401

    mem_after = proc.memory_info()
    print(f"RSS после импорта:    {mb(mem_after.rss):.1f} MB")
    print(f"Delta RSS:            {mb(mem_after.rss - mem_before.rss):.1f} MB")

    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    print(f"Tracemalloc current:  {mb(current):.2f} MB")
    print(f"Tracemalloc peak:     {mb(peak):.2f} MB")
    stats = snapshot.statistics("lineno")[:10]
    print(f"\n  Топ-10 строк по выделению памяти:")
    for stat in stats:
        print(f"    {stat}")


# ── CPU ─────────────────────────────────────────────────────────────────────

def profile_cpu():
    sep("CPU (pyinstrument)")

    try:
        from pyinstrument import Profiler
        from services.auth_service import create_access_token

        profiler = Profiler()
        profiler.start()

        for i in range(100):
            create_access_token(f"user_{i}", i)

        profiler.stop()
        print(profiler.output_text(unicode=True, color=True))

    except ImportError:
        print("pyinstrument не установлен: uv pip install pyinstrument")


# ── Endpoints ──────────────────────────────────────────────────────────────

async def profile_endpoints():
    sep("ENDPOINT LATENCY")

    try:
        from httpx import AsyncClient, ASGITransport
        from main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            endpoints = [
                ("GET", "/"),
                ("GET", "/api/health/ai"),
            ]

            for method, path in endpoints:
                times = []
                for _ in range(5):
                    start = time.perf_counter()
                    if method == "GET":
                        await client.get(path)
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)

                avg = sum(times) / len(times)
                p95 = sorted(times)[int(len(times) * 0.95)]
                print(f"  {method:4s} {path:30s}  avg={avg:.1f}ms  p95={p95:.1f}ms")

    except Exception as e:
        print(f"  Не удалось протестировать эндпоинты: {e}")


# ── Docker ─────────────────────────────────────────────────────────────────

def profile_docker():
    sep("DOCKER CONTAINERS")

    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            print(f"  {'NAME':<30s} {'CPU%':>6s} {'MEM USAGE':>14s} {'MEM%':>6s}")
            print(f"  {'-' * 30} {'-' * 6} {'-' * 14} {'-' * 6}")
            for line in lines:
                parts = line.split("\t")
                if len(parts) >= 4:
                    name = parts[0][:29]
                    cpu = parts[1].strip()
                    mem = parts[2].strip()
                    mem_pct = parts[3].strip()
                    print(f"  {name:<30s} {cpu:>6s} {mem:>14s} {mem_pct:>6s}")
        else:
            print(f"  Ошибка docker stats: {result.stderr.strip()}")
    except FileNotFoundError:
        print("  Docker не установлен")
    except subprocess.TimeoutExpired:
        print("  Таймаут docker stats")

    # Образы
    sep("DOCKER IMAGES")
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if "ai_task_manager" in line.lower():
                    parts = line.split("\t")
                    name = parts[0][:40]
                    size = parts[1].strip() if len(parts) > 1 else "?"
                    print(f"  {name:<40s} {size}")
    except Exception:
        pass


# ── Frontend ───────────────────────────────────────────────────────────────

def profile_frontend():
    sep("FRONTEND BUILD")

    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if not os.path.isdir(frontend_dir):
        print(f"  Frontend не найден: {frontend_dir}")
        return

    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            capture_output=True, text=True, cwd=frontend_dir, timeout=60
        )
        if result.returncode == 0:
            # Парсим вывод vite
            for line in result.stdout.split("\n"):
                if ".js" in line or ".css" in line or ".html" in line:
                    print(f"  {line.strip()}")

            # Считаем общий размер dist/
            dist_dir = os.path.join(frontend_dir, "dist")
            if os.path.isdir(dist_dir):
                total = 0
                for root, dirs, files in os.walk(dist_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        total += os.path.getsize(fp)
                print(f"\n  Total dist/ size: {mb(total):.2f} MB")

            stats = os.path.join(dist_dir, "stats.html")
            if os.path.exists(stats):
                print(f"  Bundle visualization: {stats}")
        else:
            print(f"  Build failed: {result.stderr[:200]}")
    except FileNotFoundError:
        print("  npm не найден")
    except subprocess.TimeoutExpired:
        print("  Таймаут сборки")


# ── All ────────────────────────────────────────────────────────────────────

async def profile_all():
    profile_system()
    profile_imports()
    profile_memory()
    profile_cpu()
    await profile_endpoints()
    profile_docker()
    profile_frontend()

    sep("SUMMARY")
    mi = proc.memory_info()
    print(f"Final RSS:            {mb(mi.rss):.1f} MB")
    print(f"Final threads:        {proc.num_threads()}")


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Профилирование ресурсов AI Task Manager"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=[
            "all", "system", "imports", "memory",
            "cpu", "endpoints", "docker", "frontend",
        ],
        help="Режим профилирования (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести результат в JSON (только imports)",
    )
    args = parser.parse_args()

    if args.mode == "all":
        asyncio.run(profile_all())
    elif args.mode == "system":
        profile_system()
    elif args.mode == "imports":
        profile_imports()
    elif args.mode == "memory":
        profile_memory()
    elif args.mode == "cpu":
        profile_cpu()
    elif args.mode == "endpoints":
        asyncio.run(profile_endpoints())
    elif args.mode == "docker":
        profile_docker()
    elif args.mode == "frontend":
        profile_frontend()


if __name__ == "__main__":
    main()
