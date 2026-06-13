from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from fastapi import FastAPI

from process_opt.api.app import create_app
from process_opt.parameters.errors import InvalidTransitionError
from process_opt.parameters.schemas import (
    ParameterItem,
    ParameterSet,
    ParameterSetCreate,
    ParameterSetWithItems,
    ParameterStatus,
)


class FakeParameterService:
    def __init__(self) -> None:
        self._sets: dict[int, ParameterSet] = {}
        self._items: dict[int, list[ParameterItem]] = {}
        self._next_id = 1
        self.confirmations: list[dict[str, Any]] = []
        self.created_drafts: list[ParameterSetCreate] = []

    def _now(self) -> datetime:
        return datetime(2026, 6, 13, 10, 0, tzinfo=UTC)

    def _make_set(
        self,
        set_id: int,
        create: ParameterSetCreate,
        status: ParameterStatus = ParameterStatus.DRAFT,
        **overrides: Any,
    ) -> ParameterSet:
        return ParameterSet(
            id=set_id,
            name=create.name,
            device_type=create.device_type,
            version=1,
            status=status,
            source=create.source,
            created_by=create.created_by,
            note=create.note,
            created_at=self._now(),
            updated_at=self._now(),
            **overrides,
        )

    def _make_items(self, set_id: int, create: ParameterSetCreate) -> list[ParameterItem]:
        return [
            ParameterItem(id=i + 1, set_id=set_id, **item.model_dump())
            for i, item in enumerate(create.items)
        ]

    async def create_draft(self, parameter_set: ParameterSetCreate) -> ParameterSet:
        self.created_drafts.append(parameter_set)
        set_id = self._next_id
        self._next_id += 1
        s = self._make_set(set_id, parameter_set)
        self._sets[set_id] = s
        self._items[set_id] = self._make_items(set_id, parameter_set)
        return s

    async def _get_or_raise(self, set_id: int) -> ParameterSet:
        s = self._sets.get(set_id)
        if s is None:
            raise ValueError(f"Parameter set {set_id} not found")
        return s

    def _update(self, set_id: int, **kwargs: Any) -> ParameterSet:
        s = self._sets[set_id]
        updated = s.model_copy(update={"updated_at": self._now(), **kwargs})
        self._sets[set_id] = updated
        return updated

    async def submit(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        s = await self._get_or_raise(set_id)
        if s.status != ParameterStatus.DRAFT:
            raise InvalidTransitionError(
                f"Invalid parameter status transition: {s.status} -> proposed"
            )
        return self._update(set_id, status=ParameterStatus.PROPOSED)

    async def approve(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        s = await self._get_or_raise(set_id)
        if s.status != ParameterStatus.PROPOSED:
            raise InvalidTransitionError(
                f"Invalid parameter status transition: {s.status} -> approved"
            )
        return self._update(
            set_id, status=ParameterStatus.APPROVED, approved_by=actor, approved_at=self._now()
        )

    async def reject(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        s = await self._get_or_raise(set_id)
        if s.status != ParameterStatus.PROPOSED:
            raise InvalidTransitionError(
                f"Invalid parameter status transition: {s.status} -> rejected"
            )
        return self._update(set_id, status=ParameterStatus.REJECTED)

    async def activate(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        s = await self._get_or_raise(set_id)
        if s.status != ParameterStatus.APPROVED:
            raise InvalidTransitionError(
                f"Invalid parameter status transition: {s.status} -> active"
            )
        for existing in list(self._sets.values()):
            if (
                existing.id != set_id
                and existing.device_type == s.device_type
                and existing.status == ParameterStatus.ACTIVE
            ):
                self._update(existing.id, status=ParameterStatus.ARCHIVED, archived_at=self._now())
        return self._update(
            set_id, status=ParameterStatus.ACTIVE, activated_by=actor, activated_at=self._now()
        )

    async def get_latest(self, device_type: str) -> ParameterSetWithItems | None:
        active = None
        for s in self._sets.values():
            if s.device_type == device_type and s.status == ParameterStatus.ACTIVE:
                if active is None or s.version > active.version:
                    active = s
        if active is None:
            return None
        items = self._items.get(active.id, [])
        item_dicts = [item.model_dump(mode="json") for item in items]
        raw = json.dumps(item_dicts, sort_keys=True, ensure_ascii=False, default=str).encode()
        checksum = hashlib.md5(raw).hexdigest()
        return ParameterSetWithItems(parameter_set=active, items=items, checksum=checksum)

    async def record_confirmation(self, **kwargs: Any) -> None:
        self.confirmations.append(kwargs)


@pytest.fixture
def sample_create() -> dict[str, Any]:
    return {
        "name": "Line A defaults",
        "device_type": "soldering-oven",
        "source": "engineering",
        "created_by": "alice",
        "note": "initial rollout",
        "items": [
            {
                "param_key": "temperature",
                "param_value": 180,
                "unit": "C",
                "data_type": "number",
                "min_value": 150,
                "max_value": 220,
                "description": "Peak temperature",
            },
            {
                "param_key": "profile",
                "param_value": {"ramp": "slow"},
                "data_type": "object",
            },
        ],
    }


@pytest.fixture
def fake_service() -> FakeParameterService:
    return FakeParameterService()


@pytest.fixture
def app(fake_service: FakeParameterService) -> "FastAPI":
    return create_app(parameter_service=fake_service)


@pytest.mark.asyncio
async def test_create_draft_returns_201_with_parameter_set(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/parameters/sets", json=sample_create)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Line A defaults"
    assert data["status"] == "draft"
    assert data["device_type"] == "soldering-oven"
    assert "id" in data


@pytest.mark.asyncio
async def test_submit_transitions_draft_to_proposed(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "proposed"


@pytest.mark.asyncio
async def test_approve_transitions_proposed_to_approved(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"})
        response = await client.post(
            f"/api/v1/parameters/sets/{set_id}/approve", json={"actor": "bob"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_transitions_proposed_to_rejected(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"})
        response = await client.post(
            f"/api/v1/parameters/sets/{set_id}/reject", json={"actor": "bob", "note": "wrong values"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_activate_transitions_approved_to_active(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"})
        await client.post(f"/api/v1/parameters/sets/{set_id}/approve", json={"actor": "bob"})
        response = await client.post(
            f"/api/v1/parameters/sets/{set_id}/activate", json={"actor": "carol"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_get_latest_returns_active_set_with_checksum(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"})
        await client.post(f"/api/v1/parameters/sets/{set_id}/approve", json={"actor": "bob"})
        await client.post(f"/api/v1/parameters/sets/{set_id}/activate", json={"actor": "carol"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/parameters/latest",
            params={"device_type": "soldering-oven", "device_id": "oven-1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["parameter_set"]["status"] == "active"
    assert len(data["items"]) == 2
    assert isinstance(data["checksum"], str)
    assert len(data["checksum"]) == 32


@pytest.mark.asyncio
async def test_get_latest_returns_404_when_no_active_set(
    app: "FastAPI",
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/parameters/latest",
            params={"device_type": "nonexistent", "device_id": "d1"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_record_confirmation_returns_204(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"})
        await client.post(f"/api/v1/parameters/sets/{set_id}/approve", json={"actor": "bob"})
        await client.post(f"/api/v1/parameters/sets/{set_id}/activate", json={"actor": "carol"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/parameters/confirmations",
            json={
                "device_id": "oven-1",
                "device_type": "soldering-oven",
                "parameter_set_id": set_id,
                "parameter_version": 1,
                "status": "applied",
                "message": "success",
            },
        )

    assert response.status_code == 204
    assert len(fake_service.confirmations) == 1


@pytest.mark.asyncio
async def test_invalid_transition_returns_structured_error(
    app: "FastAPI",
    sample_create: dict[str, Any],
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/parameters/sets", json=sample_create)
    set_id = create_resp.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/parameters/sets/{set_id}/approve", json={"actor": "bob"}
        )

    assert response.status_code == 422
    error = response.json()
    assert error["code"] == "INVALID_TRANSITION"
    assert "message" in error
    assert "suggestion" in error


@pytest.mark.asyncio
async def test_nonexistent_set_returns_structured_error(
    app: "FastAPI",
    fake_service: FakeParameterService,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/parameters/sets/99999/submit", json={"actor": "alice"}
        )

    assert response.status_code == 404
    error = response.json()
    assert error["code"] == "NOT_FOUND"
    assert "message" in error
    assert "suggestion" in error
