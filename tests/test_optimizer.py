import unittest

from app.services.optimizer import optimize_schedule


class OptimizerTestCase(unittest.TestCase):
    def setUp(self):
        self.nurses = [
            {"id": "N001", "name": "王小梅", "department_id": "ICU"},
            {"id": "N002", "name": "陳怡安", "department_id": "ICU"},
            {"id": "N003", "name": "林雅婷", "department_id": "ICU"},
        ]
        self.rules = [
            {
                "id": 1,
                "scope_type": "GLOBAL",
                "scope_id": None,
                "document": {
                    "type": "HARD",
                    "scope": "GLOBAL",
                    "clauses": {
                        "clause_1": {
                            "kind": "constraint",
                            "name": "max_consecutive_work_days",
                            "params": {"max_days": 2},
                        }
                    },
                },
                "weight": 0,
            }
        ]

    def test_optimizer_returns_assignments(self):
        result = optimize_schedule(
            nurses=self.nurses,
            rules=self.rules,
            period_from="2026-01-01",
            period_to="2026-01-02",
            coverage={"ICU": {"D": 1, "E": 1}},
            seed=3,
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(len(result["assignments"]), 6)

    def test_optimizer_reports_infeasible(self):
        result = optimize_schedule(
            nurses=self.nurses[:1],
            rules=self.rules,
            period_from="2026-01-01",
            period_to="2026-01-03",
            coverage={"ICU": {"D": 1}},
            seed=3,
        )
        self.assertEqual(result["status"], "INFEASIBLE")


if __name__ == "__main__":
    unittest.main()
