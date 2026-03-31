from __future__ import annotations

"""Resource-type contract registry router for extensibility and config/action capabilities."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.resource_type import ResourceTypeContractOut
from app.services.resource_type_service import list_resource_type_contracts

router = APIRouter()


@router.get("", response_model=list[ResourceTypeContractOut])
def read_resource_types(user=Depends(get_current_user)):
    return list_resource_type_contracts()
