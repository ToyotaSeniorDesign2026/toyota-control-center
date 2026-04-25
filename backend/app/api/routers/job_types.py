from __future__ import annotations

"""Job-type contract registry router for extensibility and config/action capabilities."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.job_type import JobTypeContractOut
from app.services.job_type_service import list_job_type_contracts

router = APIRouter()


@router.get("", response_model=list[JobTypeContractOut])
def read_job_types(user=Depends(get_current_user)):
    return list_job_type_contracts()
