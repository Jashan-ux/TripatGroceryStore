"""The caller's saved delivery addresses.

Every statement is scoped by ``profile_id`` in the ``WHERE`` clause, so an id
belonging to somebody else is indistinguishable from a missing one (404, not 403
— no existence oracle).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from app.api.deps import CustomerUserDep, SessionDep
from app.repositories import orders as repo
from app.schemas.orders import AddressIn, AddressOut
from app.services import orders as service

router = APIRouter(prefix="/addresses", tags=["addresses"])

AddressId = Annotated[uuid.UUID, Path(description="Address id")]


@router.get("", response_model=list[AddressOut], summary="My addresses")
async def list_addresses(user: CustomerUserDep, session: SessionDep) -> list[AddressOut]:
    rows = await repo.list_addresses(session, user.profile.id)
    return [service.address_out(row) for row in rows]


@router.post(
    "",
    response_model=AddressOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add an address",
)
async def create_address(
    user: CustomerUserDep, session: SessionDep, payload: AddressIn
) -> AddressOut:
    address = await service.create_address(session, user.profile, payload)
    return service.address_out(address)


@router.put("/{address_id}", response_model=AddressOut, summary="Edit an address")
async def update_address(
    user: CustomerUserDep, session: SessionDep, address_id: AddressId, payload: AddressIn
) -> AddressOut:
    address = await service.update_address(session, user.profile, address_id, payload)
    return service.address_out(address)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an address",
)
async def delete_address(
    user: CustomerUserDep, session: SessionDep, address_id: AddressId
) -> Response:
    await service.delete_address(session, user.profile, address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
