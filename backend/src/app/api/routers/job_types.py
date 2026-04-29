from __future__ import annotations

"""Job-type contract registry — discovery and dynamic form schema."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.job_type import JobTypeContractOut
from app.services.job_type_service import get_job_type_contract, list_job_type_contracts

router = APIRouter()


@router.get("", response_model=list[JobTypeContractOut])
def read_job_types(user=Depends(get_current_user)):
    contracts = list_job_type_contracts()
    return [JobTypeContractOut.from_contract(c) for c in contracts]


@router.get("/{job_type}/form-schema")
def read_form_schema(job_type: str, user=Depends(get_current_user)):
    """Return the dynamic UI form schema for a job type.

    Used by MCP App integrations to render a job creation form without
    hardcoding field definitions per type.
    """
    contract = get_job_type_contract(job_type)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown job type: '{job_type}'",
        )
    return contract.form_schema()
