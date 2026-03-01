import json
import re
from copy import deepcopy


VALID_RULE_TYPES = {"HARD", "SOFT", "PREFERENCE"}
VALID_SCOPES = {"GLOBAL", "HOSPITAL", "DEPARTMENT", "NURSE"}
VALID_CLAUSE_KINDS = {"constraint", "preference"}


def parse_scalar(raw_value: str):
    value = raw_value.strip()
    if value == "":
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse_dsl(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("DSL 不可為空白。")

    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped_line = raw_line.strip()
        if ":" not in stripped_line:
            raise ValueError(f"第 {line_number} 行缺少 ':'。")
        key, raw_value = stripped_line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if raw_value == "":
            child: dict = {}
            current[key] = child
            stack.append((indent, child))
        else:
            current[key] = parse_scalar(raw_value)
    return root


def _dump_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_\-./#]+", value):
        return value
    return json.dumps(value, ensure_ascii=False)


def dump_dsl(payload: dict, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(dump_dsl(value, indent + 2))
        else:
            lines.append(f"{prefix}{key}: {_dump_scalar(value)}")
    return "\n".join(lines)


def _status(errors: list, warnings: list) -> str:
    if errors:
        return "FAIL"
    if warnings:
        return "WARN"
    return "PASS"


def validate_rule_document(document: dict, lookup: dict | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    normalized = deepcopy(document)

    rule_type = normalized.get("type")
    scope = normalized.get("scope")
    scope_id = normalized.get("scope_id")
    clauses = normalized.get("clauses")

    if rule_type not in VALID_RULE_TYPES:
        errors.append("type 必須為 HARD、SOFT 或 PREFERENCE。")
    if scope not in VALID_SCOPES:
        errors.append("scope 必須為 GLOBAL、HOSPITAL、DEPARTMENT 或 NURSE。")
    if scope in {"DEPARTMENT", "NURSE"} and not scope_id:
        errors.append("DEPARTMENT 與 NURSE 規則必須提供 scope_id。")
    if rule_type in {"SOFT", "PREFERENCE"}:
        weight = normalized.get("weight")
        if not isinstance(weight, (int, float)) or weight <= 0:
            errors.append("SOFT/PREFERENCE 規則必須提供大於 0 的 weight。")
    if not isinstance(clauses, dict) or not clauses:
        errors.append("clauses 至少需要一條規則。")

    if lookup and scope == "DEPARTMENT" and scope_id and scope_id not in lookup.get("departments", set()):
        errors.append(f"找不到對應的科別 scope_id：{scope_id}。")
    if lookup and scope == "NURSE" and scope_id and scope_id not in lookup.get("nurses", set()):
        errors.append(f"找不到對應的護理師 scope_id：{scope_id}。")

    supported_names = {
        "max_consecutive_work_days",
        "rest_after_night",
        "max_consecutive_night",
        "avoid_night_shift_after_evening",
        "prefer_off_on_weekends",
        "custom_manual_review",
    }
    for clause_key, clause in (clauses or {}).items():
        if not isinstance(clause, dict):
            errors.append(f"{clause_key} 必須為物件。")
            continue
        kind = clause.get("kind")
        name = clause.get("name")
        params = clause.get("params")
        if kind not in VALID_CLAUSE_KINDS:
            errors.append(f"{clause_key}.kind 必須為 constraint 或 preference。")
        if not isinstance(name, str) or not name:
            errors.append(f"{clause_key}.name 必須為非空字串。")
            continue
        if not isinstance(params, dict):
            errors.append(f"{clause_key}.params 必須為物件。")
            continue
        if name not in supported_names:
            warnings.append(f"{clause_key} 使用未知規則名稱 {name}，僅會保留描述供人工確認。")
        if name == "max_consecutive_work_days":
            if int(params.get("max_days", 0)) <= 0:
                errors.append(f"{clause_key}.params.max_days 必須大於 0。")
        elif name == "rest_after_night":
            if int(params.get("days", 0)) <= 0:
                errors.append(f"{clause_key}.params.days 必須大於 0。")
        elif name == "max_consecutive_night":
            if int(params.get("max_days", 0)) <= 0:
                errors.append(f"{clause_key}.params.max_days 必須大於 0。")
        elif name == "avoid_night_shift_after_evening":
            if int(params.get("penalty", 0)) <= 0:
                errors.append(f"{clause_key}.params.penalty 必須大於 0。")
        elif name == "prefer_off_on_weekends":
            if "saturday" not in params and "sunday" not in params:
                warnings.append(f"{clause_key} 未指定 saturday/sunday，將視為兩者皆偏好休假。")

    return {
        "status": _status(errors, warnings),
        "errors": errors,
        "warnings": warnings,
        "normalized": normalized,
    }


def validate_rule_dsl(text: str, lookup: dict | None = None) -> dict:
    try:
        document = parse_dsl(text)
    except ValueError as exc:
        return {"status": "FAIL", "errors": [str(exc)], "warnings": [], "normalized": None}
    return validate_rule_document(document, lookup=lookup)
