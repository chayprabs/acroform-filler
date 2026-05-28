from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    idx = int(0.95 * (len(values) - 1))
    return sorted(values)[idx]


def run(sample_path: Path, iterations: int) -> dict[str, float | int]:
    client = TestClient(app)
    pdf_bytes = sample_path.read_bytes()
    inspect_durations: list[float] = []
    fill_durations: list[float] = []
    job_ids: list[str] = []

    for _ in range(iterations):
        start = time.perf_counter()
        response = client.post("/v1/inspect", files={"file": (sample_path.name, pdf_bytes, "application/pdf")})
        inspect_durations.append((time.perf_counter() - start) * 1000.0)
        if response.status_code == 200:
            job_ids.append(response.json()["jobId"])

    for job_id in job_ids:
        start = time.perf_counter()
        client.post(
            "/v1/fill",
            json={
                "jobId": job_id,
                "values": {},
                "regenerateAppearance": True,
                "flatten": True,
            },
        )
        fill_durations.append((time.perf_counter() - start) * 1000.0)

    return {
        "iterations": iterations,
        "inspect_p95_ms": round(p95(inspect_durations), 2),
        "fill_flatten_p95_ms": round(p95(fill_durations), 2),
        "inspect_successes": len(job_ids),
        "fill_successes": len(fill_durations),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="samples/w9.pdf")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--max-inspect-ms", type=float, default=None)
    parser.add_argument("--max-fill-ms", type=float, default=None)
    args = parser.parse_args()

    metrics = run(Path(args.sample), args.iterations)
    print(json.dumps(metrics, indent=2))
    if args.max_inspect_ms is not None and float(metrics["inspect_p95_ms"]) > args.max_inspect_ms:
        raise SystemExit(1)
    if args.max_fill_ms is not None and float(metrics["fill_flatten_p95_ms"]) > args.max_fill_ms:
        raise SystemExit(1)
