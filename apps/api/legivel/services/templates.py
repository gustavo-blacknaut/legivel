from datetime import date

from legivel.modules.base import FieldSpec


def record_fields(record, module):
    base = module.fields_for(record.kind)
    template = record.data.get("template") or {}
    return (*base, *(FieldSpec(field["name"], field["label"], field["kind"]) for field in template.get("fields", [])))


def template_issues(record, fields):
    issues = []
    for field in (record.data.get("template") or {}).get("fields", []):
        value = fields.get(field["name"], "")
        if field.get("required") and not value:
            issues.append({"field": field["name"], "message": f"Preencha {field['label']}."})
        if value and field["kind"] == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                issues.append({"field": field["name"], "message": f"Confira a data de {field['label']}."})
    return issues
