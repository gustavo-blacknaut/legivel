import json
from calendar import monthrange
from contextlib import suppress
from datetime import date, timedelta
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select

from legivel.auth.permissions import Permission
from legivel.db.base import utc_now
from legivel.db.models import AppSetting, Document, DocumentStatus, Record
from legivel.modules.registry import get_module
from legivel.services.audit import record as audit
from legivel.services.templates import template_issues
from legivel.validators.cards import parse_expiry
from legivel.validators.dates import parse_brazilian_date
from legivel.web.deps import RuntimeDep, SessionDep, permitted

router = APIRouter(prefix="/api", tags=["productivity"])
Viewer = permitted(Permission.DOCUMENTS_VIEW)
Reviewer = permitted(Permission.DOCUMENTS_REVIEW)
Admin = permitted(Permission.SETTINGS_MANAGE)
TEMPLATE_PREFIX = "document-template:"


class TemplateField(BaseModel):
    name: str = Field(pattern=r"^custom_[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    kind: Literal["text", "textarea", "date"] = "text"
    required: bool = False
    expiration: bool = False

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        if not value.strip():
            raise ValueError("Informe o nome do campo.")
        return value.strip()

    @model_validator(mode="after")
    def date_expiration(self):
        if self.expiration and self.kind != "date":
            raise ValueError("A validade deve ser um campo de data.")
        return self


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    fields: list[TemplateField] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_fields(self):
        self.name = self.name.strip()
        if not self.name or len({field.name for field in self.fields}) != len(self.fields):
            raise ValueError("Informe um nome e identificadores de campo únicos.")
        if sum(field.expiration for field in self.fields) > 1:
            raise ValueError("Escolha apenas um campo para a validade.")
        return self


def get_template(session, template_id):
    item = session.get(AppSetting, TEMPLATE_PREFIX + template_id)
    if not item:
        raise HTTPException(404, "Modelo não encontrado.")
    return item


@router.get("/document-templates")
def templates(user: Viewer, session: SessionDep):
    return [
        json.loads(item.value)
        for item in session.scalars(select(AppSetting).where(AppSetting.key.startswith(TEMPLATE_PREFIX)).order_by(AppSetting.key))
    ]


@router.post("/document-templates", status_code=201)
def create_template(body: TemplateIn, user: Admin, session: SessionDep):
    count = session.scalar(select(func.count()).select_from(AppSetting).where(AppSetting.key.startswith(TEMPLATE_PREFIX)))
    if count >= 100:
        raise HTTPException(400, "Limite de 100 modelos atingido.")
    value = {"id": uuid4().hex, **body.model_dump()}
    session.add(AppSetting(key=TEMPLATE_PREFIX + value["id"], value=json.dumps(value, ensure_ascii=False)))
    audit(session, user.id, "create", "template", None, value["id"])
    session.commit()
    return value


@router.put("/document-templates/{template_id}")
def edit_template(template_id: str, body: TemplateIn, user: Admin, session: SessionDep):
    item = get_template(session, template_id)
    value = {"id": template_id, **body.model_dump()}
    item.value = json.dumps(value, ensure_ascii=False)
    audit(session, user.id, "update", "template", None, template_id)
    session.commit()
    return value


@router.delete("/document-templates/{template_id}", status_code=204)
def delete_template(template_id: str, user: Admin, session: SessionDep):
    session.delete(get_template(session, template_id))
    audit(session, user.id, "delete", "template", None, template_id)
    session.commit()


class ApplyTemplateIn(BaseModel):
    template_id: str = Field(min_length=1, max_length=32)


@router.post("/records/{record_id}/template")
def apply_template(record_id: int, body: ApplyTemplateIn, user: Reviewer, session: SessionDep):
    item = session.scalar(select(Record).where(Record.id == record_id).with_for_update())
    if not item:
        raise HTTPException(404, "Leitura não encontrada.")
    if item.module not in ("scanner", "books"):
        raise HTTPException(400, "Modelos são usados em digitalizações e livros/textos.")
    if item.data.get("template"):
        raise HTTPException(409, "Esta leitura já tem um modelo. Os campos existentes foram preservados.")
    template = json.loads(get_template(session, body.template_id).value)
    before = dict(item.data.get("fields", {}))
    fields = {**before, **{field["name"]: "" for field in template["fields"]}}
    item.data = {**item.data, "template": template, "fields": fields}
    item.issues = get_module(item.module).validate(item.kind, fields) + template_issues(item, fields)
    item.status = DocumentStatus.PENDING_REVIEW
    item.updated_at = utc_now()
    audit(session, user.id, "template", "record", item.id, template["id"])
    session.commit()
    return {"detail": "Modelo aplicado. Confira o texto extraído e preencha os campos."}


@router.get("/review/queue")
def review_queue(
    user: Reviewer,
    session: SessionDep,
    entity: Literal["all", "document", "record"] = "all",
    limit: int = Query(default=100, ge=1, le=200),
):
    items = []
    total = 0
    for name, model in (("document", Document), ("record", Record)):
        if entity not in ("all", name):
            continue
        pending = model.status == DocumentStatus.PENDING_REVIEW
        total += session.scalar(select(func.count(model.id)).where(pending))
        created = model.processed_at if name == "document" else model.created_at
        for item in session.scalars(select(model).where(pending).order_by(created, model.id).limit(limit)):
            items.append(
                {
                    "entity": name,
                    "id": item.id,
                    "title": (item.full_name or item.doc_type.upper()) if name == "document" else (item.title or item.module),
                    "created_at": item.processed_at if name == "document" else item.created_at,
                }
            )
    items.sort(key=lambda item: (item["created_at"].isoformat(), item["entity"], item["id"]))
    return {"items": items[:limit], "total": total}


class ExpirationPreferences(BaseModel):
    days: Literal[7, 30, 60, 90] = 30


def preference_key(user):
    return f"expiration-window:{user.id}"


@router.put("/expirations/preferences")
def expiration_preferences(body: ExpirationPreferences, user: Viewer, session: SessionDep):
    key = preference_key(user)
    item = session.get(AppSetting, key)
    if item:
        item.value = str(body.days)
    else:
        session.add(AppSetting(key=key, value=str(body.days)))
    session.commit()
    return body


@router.get("/expirations")
def expirations(
    user: Viewer,
    runtime: RuntimeDep,
    session: SessionDep,
    status: Literal["all", "overdue", "due"] = "all",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    today = utc_now().astimezone(ZoneInfo(runtime.timezone)).date()
    preference = session.get(AppSetting, preference_key(user))
    days = int(preference.value) if preference else 30
    end = today + timedelta(days=days)
    items = []
    for item in session.scalars(select(Document).where(Document.valid_until <= end).order_by(Document.valid_until, Document.id)):
        items.append(
            {
                "entity": "document",
                "id": item.id,
                "title": item.full_name or item.doc_type.upper(),
                "date": item.valid_until,
                "days_left": (item.valid_until - today).days,
            }
        )
    # Templates live in encrypted record data. Decrypt one row at a time without loading image relationships.
    for item in session.scalars(select(Record).execution_options(yield_per=100)):
        template = item.data.get("template") or {}
        field = next((field for field in template.get("fields", []) if field.get("expiration")), None)
        values = item.data.get("fields", {})
        expires = None
        if field:
            with suppress(ValueError):
                expires = date.fromisoformat(values.get(field["name"], ""))
        elif item.module == "finance":
            expires = parse_brazilian_date(values.get("due_date", ""), today)
        elif item.module == "cards" and (expiry := parse_expiry(values.get("expiry", ""))):
            expires = date(expiry.year, expiry.month, monthrange(expiry.year, expiry.month)[1])
        if expires and expires <= end:
            items.append(
                {
                    "entity": "record",
                    "id": item.id,
                    "title": item.title or template.get("name") or item.module,
                    "date": expires,
                    "days_left": (expires - today).days,
                }
            )
    items.sort(key=lambda item: (item["date"], item["entity"], item["id"]))
    overdue = sum(item["days_left"] < 0 for item in items)
    selected = [
        item for item in items if status == "all" or (item["days_left"] < 0 if status == "overdue" else item["days_left"] >= 0)
    ]
    return {
        "today": today,
        "days": days,
        "overdue": overdue,
        "due": len(items) - overdue,
        "total": len(items),
        "filtered_total": len(selected),
        "page": page,
        "page_size": page_size,
        "items": selected[(page - 1) * page_size : page * page_size],
    }
