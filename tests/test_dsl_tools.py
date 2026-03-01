import unittest

from app.services.dsl_tools import parse_dsl, validate_rule_dsl


class DslToolsTestCase(unittest.TestCase):
    def test_parse_simple_dsl(self):
        document = parse_dsl(
            "\n".join(
                [
                    "type: HARD",
                    "scope: GLOBAL",
                    "clauses:",
                    "  clause_1:",
                    "    kind: constraint",
                    "    name: max_consecutive_work_days",
                    "    params:",
                    "      max_days: 6",
                ]
            )
        )
        self.assertEqual(document["type"], "HARD")
        self.assertEqual(document["clauses"]["clause_1"]["params"]["max_days"], 6)

    def test_validate_rule_dsl_success(self):
        result = validate_rule_dsl(
            "\n".join(
                [
                    "type: PREFERENCE",
                    "scope: NURSE",
                    "scope_id: N021",
                    "weight: 50",
                    "clauses:",
                    "  clause_1:",
                    "    kind: preference",
                    "    name: prefer_off_on_weekends",
                    "    params:",
                    "      saturday: true",
                    "      sunday: true",
                ]
            ),
            lookup={"nurses": {"N021"}, "departments": {"ICU"}},
        )
        self.assertEqual(result["status"], "PASS")

    def test_validate_rule_dsl_fail(self):
        result = validate_rule_dsl(
            "\n".join(
                [
                    "type: HARD",
                    "scope: DEPARTMENT",
                    "clauses:",
                    "  clause_1:",
                    "    kind: constraint",
                    "    name: max_consecutive_work_days",
                    "    params:",
                    "      max_days: 0",
                ]
            )
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
