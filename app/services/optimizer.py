import random
from collections import defaultdict
from datetime import date, timedelta

from .rule_engine import build_rule_profile


def daterange(start_text: str, end_text: str):
    current = date.fromisoformat(start_text)
    end_date = date.fromisoformat(end_text)
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _previous_shift(schedule: dict, nurse_id: str, day_index: int, days: list[str]) -> str:
    if day_index == 0:
        return "OFF"
    return schedule.get((nurse_id, days[day_index - 1]), "OFF")


def _consecutive_count(schedule: dict, nurse_id: str, day_index: int, days: list[str], target_shift: str | None = None) -> int:
    count = 0
    index = day_index - 1
    while index >= 0:
        shift = schedule.get((nurse_id, days[index]), "OFF")
        if target_shift is None:
            if shift == "OFF":
                break
        elif shift != target_shift:
            break
        count += 1
        index -= 1
    return count


def can_assign(schedule: dict, nurse_id: str, day_index: int, shift_code: str, days: list[str], profile: dict) -> bool:
    current_day = days[day_index]
    if schedule.get((nurse_id, current_day), "OFF") != "OFF":
        return False
    if shift_code == "OFF":
        return True
    previous_work_streak = _consecutive_count(schedule, nurse_id, day_index, days)
    if previous_work_streak + 1 > profile["max_consecutive_work_days"]:
        return False
    if shift_code == "N":
        previous_night_streak = _consecutive_count(schedule, nurse_id, day_index, days, "N")
        if previous_night_streak + 1 > profile["max_consecutive_night"]:
            return False
    rest_days = profile["rest_after_night"]
    if rest_days > 0:
        for offset in range(1, rest_days + 1):
            lookup_index = day_index - offset
            if lookup_index >= 0 and schedule.get((nurse_id, days[lookup_index]), "OFF") == "N":
                return False
    return True


def score_candidate(schedule: dict, nurse_id: str, nurse_stats: dict, day_index: int, shift_code: str, days: list[str], profile: dict, seed_random: random.Random) -> float:
    current_day = date.fromisoformat(days[day_index])
    score = nurse_stats[nurse_id]["total"] * 2
    if shift_code == "N":
        score += nurse_stats[nurse_id]["night"] * 5
    if current_day.weekday() >= 5 and profile["weekend_off_weight"] > 0 and shift_code != "OFF":
        score += profile["weekend_off_weight"]
    if _previous_shift(schedule, nurse_id, day_index, days) == "E" and shift_code == "N":
        score += profile["avoid_evening_to_night_weight"]
    score += seed_random.random()
    return score


def optimize_schedule(
    nurses: list[dict],
    rules: list[dict],
    period_from: str,
    period_to: str,
    coverage: dict,
    weight_multiplier: float = 1.0,
    seed: int = 7,
    progress_callback=None,
    cancel_callback=None,
):
    days = [day.isoformat() for day in daterange(period_from, period_to)]
    nurses_by_department = defaultdict(list)
    profiles = {}
    for nurse in nurses:
        nurses_by_department[nurse["department_id"]].append(nurse)
        profiles[nurse["id"]] = build_rule_profile(nurse, rules)

    schedule: dict[tuple[str, str], str] = {}
    nurse_stats = defaultdict(lambda: {"total": 0, "night": 0})
    logs: list[str] = []
    rng = random.Random(seed)
    total_steps = max(len(days) * max(sum(day_coverage.values()) for day_coverage in coverage.values()), 1)
    step_count = 0

    for day_index, current_day in enumerate(days):
        for department_id, shift_requirements in coverage.items():
            department_nurses = nurses_by_department.get(department_id, [])
            for shift_code, required in shift_requirements.items():
                for _slot in range(int(required)):
                    if cancel_callback and cancel_callback():
                        return {
                            "status": "CANCELED",
                            "assignments": [],
                            "summary": {"logs": logs},
                            "logs": logs,
                        }
                    candidates = [
                        nurse
                        for nurse in department_nurses
                        if can_assign(schedule, nurse["id"], day_index, shift_code, days, profiles[nurse["id"]])
                    ]
                    if not candidates:
                        logs.append(f"{current_day} {department_id} 的 {shift_code} 無可用人力，求解不可行。")
                        return {
                            "status": "INFEASIBLE",
                            "assignments": [],
                            "summary": {
                                "logs": logs,
                                "missing": {"date": current_day, "department_id": department_id, "shift_code": shift_code},
                            },
                            "logs": logs,
                        }
                    chosen = min(
                        candidates,
                        key=lambda nurse: score_candidate(
                            schedule,
                            nurse["id"],
                            nurse_stats,
                            day_index,
                            shift_code,
                            days,
                            profiles[nurse["id"]],
                            rng,
                        )
                        * weight_multiplier,
                    )
                    schedule[(chosen["id"], current_day)] = shift_code
                    nurse_stats[chosen["id"]]["total"] += 1
                    if shift_code == "N":
                        nurse_stats[chosen["id"]]["night"] += 1
                    logs.append(f"{current_day} {department_id} {shift_code} -> {chosen['id']} {chosen['name']}")
                    step_count += 1
                    if progress_callback:
                        best_cost = sum(stats["night"] * 5 + stats["total"] for stats in nurse_stats.values())
                        progress_callback(
                            min(int(step_count / total_steps * 100), 95),
                            f"已完成 {current_day} {department_id} {shift_code}。",
                            best_cost,
                        )
        for nurse in nurses:
            schedule.setdefault((nurse["id"], current_day), "OFF")

    assignments = [
        {
            "nurse_id": nurse["id"],
            "date": current_day,
            "shift_code": schedule[(nurse["id"], current_day)],
            "note": "",
            "source": "optimizer",
            "version_tag": f"opt-{period_from}-{period_to}",
        }
        for nurse in nurses
        for current_day in days
    ]
    summary = {
        "total_assignments": len(assignments),
        "night_counts": {nurse_id: stats["night"] for nurse_id, stats in nurse_stats.items()},
        "logs": logs[-50:],
    }
    return {"status": "SUCCEEDED", "assignments": assignments, "summary": summary, "logs": logs}
