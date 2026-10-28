#!/usr/bin/env python3
"""Summarise wall-clock timings from the OpenFOAM logs in tests/."""

from __future__ import annotations

import re
import statistics
from pathlib import Path


CASE_DIR = Path(__file__).resolve().parent
LOG_DIR = CASE_DIR / "tests"

EXECUTION_TIME_RE = re.compile(
    r"ExecutionTime\s*=\s*\S+\s+s\s+ClockTime\s*=\s*([0-9.eE+-]+)\s+s"
)


def timing_summary(log_file: Path) -> tuple[bool, list[float], tuple[float, ...] | None]:
    """Return completion state, time-step durations, and optional NVTX timings."""
    clock_times: list[float] = []
    nvtx_timings: tuple[float, ...] | None = None
    uses_petsc = False
    completed = False

    with log_file.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = EXECUTION_TIME_RE.search(line)
            if match:
                clock_times.append(float(match.group(1)))

            if "PushPop" in line and "solve" in line and nvtx_timings is None:
                fields = line.replace(",", "").split()
                try:
                    average = float(fields[3]) / 1e9
                    minimum = float(fields[5]) / 1e9
                    maximum = float(fields[6]) / 1e9
                    nvtx_timings = (minimum, maximum, average)
                except (IndexError, ValueError):
                    # Ignore unrelated or malformed PushPop lines.
                    pass

            uses_petsc |= "PETSc" in line
            completed |= line.strip() in {"End", "Finalising"}

    step_times = [
        current - previous
        for previous, current in zip(clock_times, clock_times[1:])
    ]
    if uses_petsc and step_times:
        step_times = step_times[1:]

    return completed, step_times, nvtx_timings


def main() -> int:
    if not LOG_DIR.is_dir():
        print(f"Log directory not found: {LOG_DIR}")
        return 1

    log_files = sorted(LOG_DIR.glob("*.log.*"), key=lambda path: path.stat().st_mtime)
    if not log_files:
        print(f"No '*.log.*' files found in {LOG_DIR}")
        return 1

    for log_file in log_files:
        completed, step_times, nvtx_timings = timing_summary(log_file)
        name = f"{log_file.name:<65}"

        if not completed:
            print(f"{name}   Failed!")
        elif not step_times:
            print(f"{name}   Completed, but no time-step intervals were found")
        else:
            values = [
                min(step_times),
                max(step_times),
                statistics.mean(step_times),
            ]
            if nvtx_timings is not None:
                values.extend(nvtx_timings)
            print(name + " ".join(f"{value:g}" for value in values))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
