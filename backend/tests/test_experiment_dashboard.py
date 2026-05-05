from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from app.experiments.dashboard import load_batch_dashboard, load_question_detail


class BatchDashboardTest(unittest.TestCase):
    def test_loads_scored_csv_and_computes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out_dir = root / "实验结果" / "大模型评分"
            out_dir.mkdir(parents=True)
            (out_dir / "experiment_batch_meta.json").write_text(
                json.dumps({"llm_score": True, "created_at_utc": "2026-05-05T00:00:00+00:00"}),
                encoding="utf-8",
            )
            with (out_dir / "exp_all.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "exp",
                        "question_id",
                        "block",
                        "preset_id",
                        "label",
                        "group",
                        "is_control",
                        "latency_ms",
                        "citation_count",
                        "llm_avg",
                        "composite_0_1",
                        "status",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "exp": "A",
                            "question_id": "1",
                            "block": "A_concept",
                            "preset_id": "system_full",
                            "label": "完整系统",
                            "group": "baseline",
                            "is_control": "1",
                            "latency_ms": "100",
                            "citation_count": "2",
                            "llm_avg": "4.5",
                            "composite_0_1": "0.8",
                            "status": "success",
                        },
                        {
                            "exp": "A",
                            "question_id": "1",
                            "block": "A_concept",
                            "preset_id": "baseline_rag_basic",
                            "label": "基础RAG",
                            "group": "baseline",
                            "is_control": "0",
                            "latency_ms": "80",
                            "citation_count": "1",
                            "llm_avg": "3.5",
                            "composite_0_1": "0.6",
                            "status": "success",
                        },
                        {
                            "exp": "C1",
                            "question_id": "2",
                            "block": "B_case",
                            "preset_id": "system_full",
                            "label": "完整系统",
                            "group": "baseline",
                            "is_control": "1",
                            "latency_ms": "120",
                            "citation_count": "3",
                            "llm_avg": "4.0",
                            "composite_0_1": "0.7",
                            "status": "success",
                        },
                        {
                            "exp": "C1",
                            "question_id": "2",
                            "block": "B_case",
                            "preset_id": "ablation_no_mmr",
                            "label": "去掉MMR",
                            "group": "ablation",
                            "is_control": "0",
                            "latency_ms": "110",
                            "citation_count": "2",
                            "llm_avg": "",
                            "composite_0_1": "0.5",
                            "status": "failed:timeout",
                        },
                    ]
                )

            dashboard = load_batch_dashboard(root)

            self.assertTrue(dashboard.available)
            self.assertEqual(dashboard.source_kind, "大模型评分")
            self.assertEqual(dashboard.summary.total_questions, 2)
            self.assertEqual(dashboard.summary.total_rows, 4)
            self.assertEqual(dashboard.summary.success_rows, 3)
            self.assertAlmostEqual(dashboard.summary.success_rate, 0.75)
            self.assertTrue(dashboard.summary.has_llm_scores)
            self.assertEqual(dashboard.meta.get("llm_score"), True)

            system = next(x for x in dashboard.preset_summaries if x.preset_id == "system_full")
            self.assertAlmostEqual(system.avg_composite, 0.75)
            self.assertAlmostEqual(system.avg_llm, 4.25)

            c1_delta = next(x for x in dashboard.ablation_deltas if x.exp == "C1")
            self.assertEqual(c1_delta.ablation_preset_id, "ablation_no_mmr")
            self.assertAlmostEqual(c1_delta.composite_delta, 0.2)
            self.assertIn("基线对比", dashboard.ai_summary)
            self.assertEqual(len(dashboard.question_index), 2)

            d1 = load_question_detail(1, root)
            self.assertTrue(d1.available)
            self.assertEqual(len(d1.arms), 2)
            self.assertEqual(d1.arms[0].exp, "A")

    def test_returns_unavailable_when_csv_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dashboard = load_batch_dashboard(Path(td))

            self.assertFalse(dashboard.available)
            self.assertIn("run_experiment_batch.py", dashboard.message)


if __name__ == "__main__":
    unittest.main()
