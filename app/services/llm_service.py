import json
import re
import urllib.error
import urllib.request

from .dsl_tools import dump_dsl, parse_dsl, validate_rule_document, validate_rule_dsl


def _extract_first_number(text: str, default: int) -> int:
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return default


def _extract_number_by_pattern(text: str, pattern: str, default: int) -> int:
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    return default


def _fallback_document(text: str, scope: str, scope_id: str | None, rule_type: str) -> dict:
    clauses: dict = {}
    clause_index = 1
    if "連續上班" in text:
        clauses[f"clause_{clause_index}"] = {
            "kind": "constraint",
            "name": "max_consecutive_work_days",
            "params": {"max_days": _extract_first_number(text, 6)},
        }
        clause_index += 1
    if ("夜班後" in text or "大夜後" in text) and ("休" in text or "休息" in text):
        clauses[f"clause_{clause_index}"] = {
            "kind": "constraint",
            "name": "rest_after_night",
            "params": {"days": _extract_number_by_pattern(text, r"(?:休息|休)\s*(\d+)\s*天", 1)},
        }
        clause_index += 1
    if "連續大夜" in text or "連續夜班" in text:
        clauses[f"clause_{clause_index}"] = {
            "kind": "constraint",
            "name": "max_consecutive_night",
            "params": {"max_days": _extract_number_by_pattern(text, r"(?:連續大夜|連續夜班)[^\d]{0,8}(\d+)\s*天", 2)},
        }
        clause_index += 1
    if "小夜" in text and "大夜" in text and ("避免" in text or "盡量" in text):
        clauses[f"clause_{clause_index}"] = {
            "kind": "preference",
            "name": "avoid_night_shift_after_evening",
            "params": {"penalty": 1},
        }
        clause_index += 1
    if ("週末" in text or "週六" in text or "週日" in text or "假日" in text) and ("休" in text or "OFF" in text):
        clauses[f"clause_{clause_index}"] = {
            "kind": "preference",
            "name": "prefer_off_on_weekends",
            "params": {"saturday": True, "sunday": True},
        }
        clause_index += 1
    if not clauses:
        clauses["clause_1"] = {
            "kind": "preference" if rule_type != "HARD" else "constraint",
            "name": "custom_manual_review",
            "params": {"raw_text": text},
        }

    document = {
        "type": rule_type,
        "scope": scope,
        "clauses": clauses,
    }
    if scope_id:
        document["scope_id"] = scope_id
    if rule_type in {"SOFT", "PREFERENCE"}:
        document["weight"] = 30 if rule_type == "SOFT" else 50
    return document


def reverse_translate(document: dict) -> str:
    phrases: list[str] = []
    for clause in document.get("clauses", {}).values():
        name = clause.get("name")
        params = clause.get("params", {})
        if name == "max_consecutive_work_days":
            phrases.append(f"連續上班不得超過 {params.get('max_days', 6)} 天")
        elif name == "rest_after_night":
            phrases.append(f"夜班後至少休息 {params.get('days', 1)} 天")
        elif name == "max_consecutive_night":
            phrases.append(f"連續大夜不得超過 {params.get('max_days', 2)} 天")
        elif name == "avoid_night_shift_after_evening":
            phrases.append("盡量避免小夜後直接接大夜")
        elif name == "prefer_off_on_weekends":
            phrases.append("週末盡量安排休假")
        elif name == "custom_manual_review":
            phrases.append(f"需要人工確認：{params.get('raw_text', '')}")
    if not phrases:
        return "目前無法反向翻譯，請人工確認 DSL。"
    return "；".join(phrases) + "。"


def _extract_output_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "".join(chunks).strip()


def _call_openai_responses(settings: dict, prompt: str) -> str | None:
    api_key = settings.get("openai_api_key") or ""
    if not api_key or settings.get("llm_mode") != "openai":
        return None
    body = {
        "model": settings.get("openai_model") or "gpt-4.1-mini",
        "input": prompt,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return _extract_output_text(payload)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


class LLMService:
    def __init__(self, repository):
        self.repository = repository

    def _lookup(self) -> dict:
        return {
            "departments": {item["id"] for item in self.repository.list_master("departments")},
            "nurses": {item["id"] for item in self.repository.list_master("nurses")},
        }

    def translate_rule(self, text: str, scope: str, scope_id: str | None, rule_type: str) -> dict:
        settings = self.repository.get_settings()
        prompt = (
            "請將以下護理排班規則轉成 YAML-like DSL，格式固定包含 type、scope、scope_id(若有)、weight(若需要)、clauses。\n"
            f"規則：{text}"
        )
        raw_output = _call_openai_responses(settings, prompt)
        if raw_output:
            try:
                document = parse_dsl(raw_output)
            except ValueError:
                document = _fallback_document(text, scope, scope_id, rule_type)
        else:
            document = _fallback_document(text, scope, scope_id, rule_type)
        document["type"] = rule_type
        document["scope"] = scope
        if scope_id:
            document["scope_id"] = scope_id
        report = validate_rule_document(document, lookup=self._lookup())
        dsl_text = dump_dsl(document)
        reverse_text = reverse_translate(document)
        return {
            "dsl_text": dsl_text,
            "reverse_text": reverse_text,
            "validation_report": report,
        }

    def translate_rule_events(self, text: str, scope: str, scope_id: str | None, rule_type: str):
        result = self.translate_rule(text, scope, scope_id, rule_type)
        for line in result["dsl_text"].splitlines(keepends=True):
            yield {"event": "token", "data": {"chunk": line}}
        yield {"event": "validation", "data": result["validation_report"]}
        yield {"event": "reverse", "data": {"text": result["reverse_text"]}}
        yield {
            "event": "result",
            "data": {
                "dsl_text": result["dsl_text"],
                "reverse_text": result["reverse_text"],
                "validation_report": result["validation_report"],
            },
        }

    def validate_manual_dsl(self, dsl_text: str) -> dict:
        report = validate_rule_dsl(dsl_text, lookup=self._lookup())
        document = report.get("normalized") or {}
        reverse_text = reverse_translate(document) if document else "DSL 驗證失敗，無法反向翻譯。"
        return {"validation_report": report, "reverse_text": reverse_text}
