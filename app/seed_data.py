from datetime import date, timedelta


DEFAULT_DEPARTMENTS = [
    {"id": "ICU", "name": "加護病房", "description": "重症照護單位", "active": 1},
    {"id": "ER", "name": "急診", "description": "急診照護單位", "active": 1},
    {"id": "WARD-A", "name": "一般病房 A", "description": "一般病房示例", "active": 1},
]

DEFAULT_SHIFT_CODES = [
    {"id": "D", "name": "日班", "start_time": "08:00", "end_time": "16:00", "color": "#DBEAFE", "active": 1},
    {"id": "E", "name": "小夜", "start_time": "16:00", "end_time": "00:00", "color": "#D1FAE5", "active": 1},
    {"id": "N", "name": "大夜", "start_time": "00:00", "end_time": "08:00", "color": "#EDE9FE", "active": 1},
    {"id": "OFF", "name": "休假", "start_time": "00:00", "end_time": "23:59", "color": "#FEE2E2", "active": 1},
]

DEFAULT_JOB_LEVELS = [
    {"id": "N1", "name": "N1", "description": "基礎護理能力", "active": 1},
    {"id": "N2", "name": "N2", "description": "進階護理能力", "active": 1},
    {"id": "N3", "name": "N3", "description": "資深護理能力", "active": 1},
    {"id": "N4", "name": "N4", "description": "專家護理能力", "active": 1},
]

DEFAULT_SKILLS = [
    {"id": "ICU", "name": "ICU", "description": "加護病房照護", "active": 1},
    {"id": "ER", "name": "ER", "description": "急診照護", "active": 1},
    {"id": "VENT", "name": "VENT", "description": "呼吸器照護", "active": 1},
]

DEFAULT_NURSES = [
    {"id": "N001", "name": "王小梅", "department_id": "ICU", "job_level_id": "N3", "skills": ["ICU", "VENT"]},
    {"id": "N002", "name": "陳怡安", "department_id": "ICU", "job_level_id": "N2", "skills": ["ICU"]},
    {"id": "N003", "name": "林雅婷", "department_id": "ICU", "job_level_id": "N1", "skills": []},
    {"id": "N004", "name": "張惠雯", "department_id": "ICU", "job_level_id": "N2", "skills": ["VENT"]},
    {"id": "N005", "name": "蔡佩珊", "department_id": "ICU", "job_level_id": "N4", "skills": ["ICU", "VENT"]},
    {"id": "N006", "name": "李佳蓉", "department_id": "ICU", "job_level_id": "N2", "skills": ["ICU"]},
    {"id": "N007", "name": "黃詩涵", "department_id": "ICU", "job_level_id": "N1", "skills": []},
    {"id": "N008", "name": "許雅雯", "department_id": "ICU", "job_level_id": "N3", "skills": ["ICU"]},
    {"id": "N009", "name": "周欣怡", "department_id": "ICU", "job_level_id": "N2", "skills": []},
    {"id": "N010", "name": "鄭安琪", "department_id": "ICU", "job_level_id": "N1", "skills": []},
    {"id": "N011", "name": "何婉婷", "department_id": "ICU", "job_level_id": "N2", "skills": ["VENT"]},
    {"id": "N012", "name": "郭品妤", "department_id": "ICU", "job_level_id": "N3", "skills": ["ICU"]},
    {"id": "N013", "name": "楊子晴", "department_id": "ER", "job_level_id": "N2", "skills": ["ER"]},
    {"id": "N014", "name": "吳思妤", "department_id": "ER", "job_level_id": "N1", "skills": ["ER"]},
    {"id": "N015", "name": "謝佳穎", "department_id": "ER", "job_level_id": "N3", "skills": ["ER"]},
    {"id": "N016", "name": "沈佩儀", "department_id": "ER", "job_level_id": "N2", "skills": []},
    {"id": "N017", "name": "趙怡君", "department_id": "ER", "job_level_id": "N1", "skills": []},
    {"id": "N018", "name": "鍾雨潔", "department_id": "ER", "job_level_id": "N2", "skills": ["ER"]},
    {"id": "N019", "name": "施婉如", "department_id": "ER", "job_level_id": "N4", "skills": ["ER"]},
    {"id": "N020", "name": "曾怡蓁", "department_id": "ER", "job_level_id": "N2", "skills": []},
    {"id": "N021", "name": "彭心妤", "department_id": "ER", "job_level_id": "N1", "skills": []},
    {"id": "N022", "name": "方宜庭", "department_id": "ER", "job_level_id": "N3", "skills": ["ER"]},
    {"id": "N023", "name": "葉采薇", "department_id": "WARD-A", "job_level_id": "N2", "skills": []},
    {"id": "N024", "name": "高郁婷", "department_id": "WARD-A", "job_level_id": "N1", "skills": []},
    {"id": "N025", "name": "邱筱晴", "department_id": "WARD-A", "job_level_id": "N2", "skills": []},
    {"id": "N026", "name": "宋依珊", "department_id": "WARD-A", "job_level_id": "N3", "skills": []},
    {"id": "N027", "name": "盧語嫻", "department_id": "WARD-A", "job_level_id": "N1", "skills": []},
    {"id": "N028", "name": "梁思瑤", "department_id": "WARD-A", "job_level_id": "N2", "skills": []},
    {"id": "N029", "name": "姚欣蓉", "department_id": "WARD-A", "job_level_id": "N4", "skills": []},
    {"id": "N030", "name": "簡語彤", "department_id": "WARD-A", "job_level_id": "N2", "skills": []},
]

DEFAULT_RULES = [
    {
        "title": "全域連續上班上限",
        "scope_type": "GLOBAL",
        "scope_id": None,
        "rule_type": "HARD",
        "priority": 100,
        "source_nl": "連續上班天數不得超過 6 天。",
        "dsl_text": "\n".join(
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
        ),
    },
    {
        "title": "夜班後至少休 1 天",
        "scope_type": "DEPARTMENT",
        "scope_id": "ICU",
        "rule_type": "HARD",
        "priority": 120,
        "source_nl": "夜班後至少休息 1 天。",
        "dsl_text": "\n".join(
            [
                "type: HARD",
                "scope: DEPARTMENT",
                "scope_id: ICU",
                "clauses:",
                "  clause_1:",
                "    kind: constraint",
                "    name: rest_after_night",
                "    params:",
                "      days: 1",
            ]
        ),
    },
    {
        "title": "避免小夜後直接接大夜",
        "scope_type": "DEPARTMENT",
        "scope_id": "ICU",
        "rule_type": "SOFT",
        "priority": 90,
        "source_nl": "盡量避免小夜之後直接接大夜。",
        "dsl_text": "\n".join(
            [
                "type: SOFT",
                "scope: DEPARTMENT",
                "scope_id: ICU",
                "weight: 30",
                "clauses:",
                "  clause_1:",
                "    kind: preference",
                "    name: avoid_night_shift_after_evening",
                "    params:",
                "      penalty: 1",
            ]
        ),
    },
    {
        "title": "ER 新進護理師週末盡量休假",
        "scope_type": "NURSE",
        "scope_id": "N021",
        "rule_type": "PREFERENCE",
        "priority": 80,
        "source_nl": "N021 週六與週日盡量排休。",
        "dsl_text": "\n".join(
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
    },
]

DEFAULT_PROJECT = {
    "name": "示範排班專案",
    "description": "依照規格初始化的護理排班示範資料。",
}

DEFAULT_UI_STATE = {
    "calendar_from": "2026-01-01",
    "calendar_to": "2026-01-14",
    "department_id": "ICU",
    "coverage": {
        "ICU": {"D": 3, "E": 2, "N": 2},
        "ER": {"D": 3, "E": 2, "N": 2},
        "WARD-A": {"D": 2, "E": 1, "N": 1},
    },
}


def daterange(start_text: str, end_text: str):
    current = date.fromisoformat(start_text)
    end_date = date.fromisoformat(end_text)
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def generate_default_assignments(start_text: str, end_text: str, nurses: list[dict]) -> list[dict]:
    patterns = [
        ["D", "D", "E", "E", "N", "OFF", "OFF"],
        ["E", "E", "N", "OFF", "OFF", "D", "D"],
        ["N", "OFF", "OFF", "D", "D", "E", "E"],
        ["D", "E", "N", "OFF", "D", "E", "OFF"],
        ["OFF", "D", "D", "E", "E", "N", "OFF"],
    ]
    assignments: list[dict] = []
    days = list(daterange(start_text, end_text))
    for nurse_index, nurse in enumerate(nurses):
        pattern = patterns[nurse_index % len(patterns)]
        for day_index, current_day in enumerate(days):
            shift_code = pattern[(day_index + nurse_index) % len(pattern)]
            assignments.append(
                {
                    "nurse_id": nurse["id"],
                    "date": current_day.isoformat(),
                    "shift_code": shift_code,
                    "note": "",
                    "source": "seed",
                    "version_tag": "seed-v1",
                }
            )
    return assignments
