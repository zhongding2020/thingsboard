from __future__ import annotations

import hashlib
import json
from typing import Any

from process_opt.parameters.repository import ParameterRepository
from process_opt.parameters.schemas import (
    ParameterItem,
    ParameterSet,
    ParameterSetCreate,
    ParameterSetWithItems,
    ParameterStatus,
)
from process_opt.parameters.state_machine import validate_transition


class ParameterService:
    def __init__(self, repo: ParameterRepository) -> None:
        self._repo = repo

    async def create_draft(self, parameter_set: ParameterSetCreate) -> ParameterSet:
        draft = await self._repo.create_set(parameter_set)
        await self._repo.add_event(draft.id, "create", parameter_set.created_by)
        return draft

    async def submit(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        current = await self._get_or_raise(set_id)
        validate_transition(current.status, ParameterStatus.PROPOSED)
        result = await self._repo.update_status(set_id, ParameterStatus.PROPOSED, actor, note)
        assert result is not None
        return result

    async def approve(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        current = await self._get_or_raise(set_id)
        validate_transition(current.status, ParameterStatus.APPROVED)
        result = await self._repo.update_status(set_id, ParameterStatus.APPROVED, actor, note)
        assert result is not None
        return result

    async def reject(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        current = await self._get_or_raise(set_id)
        validate_transition(current.status, ParameterStatus.REJECTED)
        result = await self._repo.update_status(set_id, ParameterStatus.REJECTED, actor, note)
        assert result is not None
        return result

    async def activate(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        current = await self._get_or_raise(set_id)
        validate_transition(current.status, ParameterStatus.ACTIVE)
        old_active = await self._repo.get_latest_active(current.device_type)
        old_active_id: int | None = None
        if old_active is not None and old_active.id != set_id:
            validate_transition(old_active.status, ParameterStatus.ARCHIVED)
            old_active_id = old_active.id
        return await self._repo.replace_with_active(set_id, old_active_id, actor, note)

    async def get_latest(self, device_type: str) -> ParameterSetWithItems | None:
        active = await self._repo.get_latest_active(device_type)
        if active is None:
            return None
        items = await self._repo.list_items(active.id)
        checksum = self._compute_checksum(items)
        return ParameterSetWithItems(parameter_set=active, items=items, checksum=checksum)

    async def record_confirmation(self, **kwargs: Any) -> None:
        await self._repo.insert_confirmation(**kwargs)

    async def _get_or_raise(self, set_id: int) -> ParameterSet:
        s = await self._repo.get_set(set_id)
        if s is None:
            raise ValueError(f"Parameter set {set_id} not found")
        return s

    @staticmethod
    def _compute_checksum(items: list[ParameterItem]) -> str:
        item_dicts = [item.model_dump(mode="json") for item in items]
        raw = json.dumps(item_dicts, sort_keys=True, ensure_ascii=False, default=str).encode()
        return hashlib.md5(raw).hexdigest()
