from datetime import UTC, datetime, timedelta

import pytest

from legivel.db.models import AuditLog, Document, DocumentStatus, Person
from tests.conftest import login


@pytest.fixture
def populated(client):
    login(client)
    base = datetime(2026, 1, 10, 12, tzinfo=UTC)
    with client.app_state.session_factory() as session:
        for index in range(120):
            created_at = base + timedelta(days=index)
            person = Person(full_name=f"PESSOA FICTICIA {index:03d}", cpf=f"{index:011d}", created_at=created_at)
            status = DocumentStatus.PENDING_REVIEW if index % 3 == 0 else DocumentStatus.REVIEWED
            doc_type = "cnh" if index % 4 == 0 else "rg"
            person.documents.append(
                Document(
                    doc_type=doc_type,
                    status=status,
                    full_name=person.full_name,
                    cpf=person.cpf,
                    processed_at=base + timedelta(days=index),
                    field_confidence={},
                    extra_fields={},
                )
            )
            session.add(person)
        session.commit()
    return client


def test_people_are_paginated_with_total(populated):
    first = populated.get("/api/people", params={"page_size": 50}).json()
    assert first["total"] == 120
    assert len(first["items"]) == 50
    last = populated.get("/api/people", params={"page_size": 50, "page": 3}).json()
    assert len(last["items"]) == 20
    ids = {item["id"] for item in first["items"]} | {item["id"] for item in last["items"]}
    assert len(ids) == 70


def test_people_filters_by_text_status_type_and_period(populated):
    def total(**params):
        return populated.get("/api/people", params=params).json()["total"]

    assert total(q="ficticia 007") == 1
    assert total(q="00000000042") == 1
    assert total(status="pending_review") == 40
    assert total(status="reviewed") == 80
    assert total(doc_type="cnh") == 30
    assert total(**{"from": "2026-01-10", "to": "2026-01-19"}) == 10


def test_people_sorting(populated):
    by_name = populated.get("/api/people", params={"sort": "name", "order": "asc", "page_size": 3}).json()["items"]
    assert [item["full_name"] for item in by_name] == ["PESSOA FICTICIA 000", "PESSOA FICTICIA 001", "PESSOA FICTICIA 002"]
    by_status = populated.get("/api/people", params={"sort": "status", "order": "asc", "page_size": 40}).json()["items"]
    assert all(item["status"] == "pending_review" for item in by_status)
    newest = populated.get("/api/people", params={"page_size": 1}).json()["items"][0]
    assert newest["full_name"] == "PESSOA FICTICIA 119"


def test_person_detail_includes_documents_and_counts(populated):
    person_id = populated.get("/api/people", params={"page_size": 1}).json()["items"][0]["id"]
    detail = populated.get(f"/api/people/{person_id}").json()
    assert detail["documents"] == 1
    assert detail["images"] == 0
    assert len(detail["document_list"]) == 1
    assert populated.get("/api/people/999999").status_code == 404


def test_documents_list_filters(populated):
    page = populated.get("/api/documents", params={"doc_type": "cnh", "status": "pending_review"}).json()
    assert page["total"] == 10
    assert all(item["doc_type"] == "cnh" and item["status"] == "pending_review" for item in page["items"])


def test_audit_log_lists_actions_with_user_names(populated):
    with populated.app_state.session_factory() as session:
        session.add(AuditLog(user_id=None, action="delete", entity="document", entity_id=1))
        session.commit()
    entries = populated.get("/api/audit").json()
    assert entries["total"] >= 2
    login_entry = next(item for item in entries["items"] if item["action"] == "login")
    assert login_entry["user"] == "Operador"
    assert populated.get("/api/audit", params={"action": "delete"}).json()["total"] == 1


def test_page_size_is_bounded(populated):
    assert populated.get("/api/people", params={"page_size": 1000}).status_code == 422
