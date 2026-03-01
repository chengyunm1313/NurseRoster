from collections import defaultdict
from datetime import date, timedelta


def daterange(start_text: str, end_text: str):
    current = date.fromisoformat(start_text)
    end_date = date.fromisoformat(end_text)
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def rule_applies_to_nurse(rule: dict, nurse: dict) -> bool:
    scope_type = rule["scope_type"]
    if scope_type == "GLOBAL":
        return True
    if scope_type == "DEPARTMENT":
        return rule.get("scope_id") == nurse["department_id"]
    if scope_type == "NURSE":
        return rule.get("scope_id") == nurse["id"]
    return True


def build_rule_profile(nurse: dict, rules: list[dict]) -> dict:
    profile = {
        "max_consecutive_work_days": 6,
        "rest_after_night": 0,
        "max_consecutive_night": 2,
        "weekend_off_weight": 0,
        "avoid_evening_to_night_weight": 0,
        "applied_rule_ids": [],
    }
    for rule in rules:
        if not rule_applies_to_nurse(rule, nurse):
            continue
        profile["applied_rule_ids"].append(rule["id"])
        for clause in rule["document"].get("clauses", {}).values():
            name = clause.get("name")
            params = clause.get("params", {})
            weight = int(rule.get("weight") or rule.get("document", {}).get("weight") or 0)
            if name == "max_consecutive_work_days":
                profile["max_consecutive_work_days"] = min(profile["max_consecutive_work_days"], int(params.get("max_days", 6)))
            elif name == "rest_after_night":
                profile["rest_after_night"] = max(profile["rest_after_night"], int(params.get("days", 0)))
            elif name == "max_consecutive_night":
                profile["max_consecutive_night"] = min(profile["max_consecutive_night"], int(params.get("max_days", 2)))
            elif name == "prefer_off_on_weekends":
                profile["weekend_off_weight"] = max(profile["weekend_off_weight"], weight or 30)
            elif name == "avoid_night_shift_after_evening":
                profile["avoid_evening_to_night_weight"] = max(profile["avoid_evening_to_night_weight"], weight or 20)
    return profile


def build_schedule_map(assignments: list[dict]) -> dict:
    schedule = defaultdict(dict)
    for assignment in assignments:
        schedule[assignment["nurse_id"]][assignment["date"]] = assignment["shift_code_id"]
    return schedule


def evaluate_conflicts(
    nurses: list[dict],
    assignments: list[dict],
    rules: list[dict],
    start_text: str,
    end_text: str,
    coverage: dict | None = None,
) -> list[dict]:
    schedule = build_schedule_map(assignments)
    nurses_by_id = {nurse["id"]: nurse for nurse in nurses}
    conflicts: list[dict] = []
    coverage = coverage or {}
    days = [current.isoformat() for current in daterange(start_text, end_text)]

    for nurse in nurses:
        profile = build_rule_profile(nurse, rules)
        working_streak = 0
        night_streak = 0
        previous_shift = "OFF"
        previous_days: list[str] = []
        for current_day in days:
            shift = schedule.get(nurse["id"], {}).get(current_day, "OFF")
            if shift != "OFF":
                working_streak += 1
            else:
                working_streak = 0
            if shift == "N":
                night_streak += 1
            else:
                night_streak = 0
            if working_streak > profile["max_consecutive_work_days"]:
                conflicts.append(
                    {
                        "type": "rule",
                        "rule_ids": profile["applied_rule_ids"],
                        "nurse_id": nurse["id"],
                        "date": current_day,
                        "message": f"{nurse['name']} 連續上班超過 {profile['max_consecutive_work_days']} 天。",
                    }
                )
            if night_streak > profile["max_consecutive_night"]:
                conflicts.append(
                    {
                        "type": "rule",
                        "rule_ids": profile["applied_rule_ids"],
                        "nurse_id": nurse["id"],
                        "date": current_day,
                        "message": f"{nurse['name']} 連續大夜超過 {profile['max_consecutive_night']} 天。",
                    }
                )
            if shift != "OFF" and profile["rest_after_night"] > 0:
                recent_nights = previous_days[-profile["rest_after_night"] :]
                if any(schedule.get(nurse["id"], {}).get(day) == "N" for day in recent_nights):
                    conflicts.append(
                        {
                            "type": "rule",
                            "rule_ids": profile["applied_rule_ids"],
                            "nurse_id": nurse["id"],
                            "date": current_day,
                            "message": f"{nurse['name']} 夜班後未滿足休息 {profile['rest_after_night']} 天。",
                        }
                    )
            if previous_shift == "E" and shift == "N" and profile["avoid_evening_to_night_weight"] > 0:
                conflicts.append(
                    {
                        "type": "preference",
                        "rule_ids": profile["applied_rule_ids"],
                        "nurse_id": nurse["id"],
                        "date": current_day,
                        "message": f"{nurse['name']} 出現小夜接大夜的偏好衝突。",
                    }
                )
            previous_shift = shift
            previous_days.append(current_day)

    if coverage:
        by_day_department = defaultdict(lambda: defaultdict(int))
        for assignment in assignments:
            nurse = nurses_by_id.get(assignment["nurse_id"])
            if not nurse or assignment["shift_code_id"] == "OFF":
                continue
            by_day_department[(assignment["date"], nurse["department_id"])][assignment["shift_code_id"]] += 1
        for current_day in days:
            for department_id, shift_requirements in coverage.items():
                actual = by_day_department[(current_day, department_id)]
                for shift_code, required in shift_requirements.items():
                    if actual.get(shift_code, 0) < int(required):
                        conflicts.append(
                            {
                                "type": "coverage",
                                "department_id": department_id,
                                "date": current_day,
                                "message": f"{department_id} {current_day} 的 {shift_code} 需求不足，需求 {required}、實際 {actual.get(shift_code, 0)}。",
                            }
                        )
    return conflicts
