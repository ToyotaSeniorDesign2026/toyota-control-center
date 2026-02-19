from fastapi import APIRouter, Depends

from app.api.deps import get_db, require_domain_admin
from app.schemas.integrations import GithubActionsWebhookPayload, GithubWebhookAck
from app.services.github_actions_service import handle_github_actions_webhook

router = APIRouter()


@router.post("/github/actions/webhook", response_model=GithubWebhookAck)
def github_actions_webhook(
    payload: GithubActionsWebhookPayload,
    db=Depends(get_db),
    admin=Depends(require_domain_admin),
):
    # For the skeleton, we protect this route with admin auth.
    # Later, replace with GitHub webhook signature verification.
    return handle_github_actions_webhook(db, payload)
