from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _safe_div(a: float, b: float) -> float:
    return round(a / b, 4) if b else 0.0


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = (line or "").strip()
            if not s:
                continue
            try:
                yield json.loads(s)
            except Exception:
                continue


def _extract(row: Dict[str, Any]) -> Tuple[str, str, str, float, int, str]:
    exp_id = str(row.get("experiment_id") or "unknown")
    exp_group = str(row.get("experiment_group") or "")
    exp_name = str(row.get("experiment_name") or "")
    rs = row.get("runtime_summary") or {}
    elapsed = float(rs.get("elapsed_sec") or 0.0) if isinstance(rs, dict) else 0.0
    evidence_count = int(rs.get("evidence_count") or 0) if isinstance(rs, dict) else 0
    coverage = str(rs.get("coverage") or "") if isinstance(rs, dict) else ""
    return exp_id, exp_group, exp_name, elapsed, evidence_count, coverage


def summarize_turns(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "n": 0,
        "elapsed_sum": 0.0,
        "evidence_sum": 0,
        "coverage_counter": Counter(),
        "group": "",
        "name": "",
    })
    for r in rows:
        exp_id, exp_group, exp_name, elapsed, evidence_count, coverage = _extract(r)
        b = bucket[exp_id]
        b["n"] += 1
        b["elapsed_sum"] += float(elapsed)
        b["evidence_sum"] += int(evidence_count)
        if coverage:
            b["coverage_counter"][coverage] += 1
        if exp_group and not b["group"]:
            b["group"] = exp_group
        if exp_name and not b["name"]:
            b["name"] = exp_name

    out: List[Dict[str, Any]] = []
    for exp_id, b in bucket.items():
        n = int(b["n"])
        cov = b["coverage_counter"]
        out.append({
            "experiment_id": exp_id,
            "group": b["group"],
            "name": b["name"],
            "turns": n,
            "avg_elapsed_sec": _safe_div(b["elapsed_sum"], n),
            "avg_evidence_count": _safe_div(float(b["evidence_sum"]), n),
            "coverage_full_ratio": _safe_div(float(cov.get("full", 0)), n),
            "coverage_partial_ratio": _safe_div(float(cov.get("partial", 0)), n),
            "coverage_none_ratio": _safe_div(float(cov.get("none", 0)), n),
        })
    out.sort(key=lambda x: (x.get("group") or "", x.get("experiment_id") or ""))
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    in_path = project_root / "实验记录" / "qa_experiment_turns.jsonl"
    out_path = project_root / "实验记录" / "experiment_summary.csv"

    rows = list(_iter_jsonl(in_path))
    summary = summarize_turns(rows)
    write_csv(out_path, summary)

    print(f"input:  {in_path}")
    print(f"turns:  {len(rows)}")
    print(f"groups: {len(summary)}")
    print(f"output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

