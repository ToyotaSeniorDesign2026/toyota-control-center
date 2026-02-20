from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_db
from app.schemas.discovery import (
    EnvironmentComparisonOut,
    InsightsRiskDistributionOut,
    InsightsSummaryOut,
    InsightsTrendsOut,
    ProductivityImpactOut,
    TopResourceOut,
)
from app.schemas.resource import ResourceOut
from app.services.discovery_service import (
    get_environment_comparison,
    get_insights_summary,
    get_insights_trends,
    get_productivity_impact,
    get_risk_distribution,
    get_top_resources,
)
from app.services.resource_service import search_resources

router = APIRouter()


@router.get("/resources", response_model=list[ResourceOut])
def discover_resources(
    q: str | None = Query(default=None),
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    env: str | None = Query(default=None),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return search_resources(db, user, q=q, type=type, status=status, env=env)


@router.get("/insights/summary", response_model=InsightsSummaryOut)
def insights_summary(db=Depends(get_db), user=Depends(get_current_user)):
    return get_insights_summary(db, user)


@router.get("/insights/trends", response_model=InsightsTrendsOut)
def insights_trends(db=Depends(get_db), user=Depends(get_current_user)):
    return get_insights_trends(db, user)


@router.get("/insights/risk-distribution", response_model=InsightsRiskDistributionOut)
def insights_risk_distribution(db=Depends(get_db), user=Depends(get_current_user)):
    return get_risk_distribution(db, user)


@router.get("/insights/productivity", response_model=ProductivityImpactOut)
def insights_productivity(db=Depends(get_db), user=Depends(get_current_user)):
    return get_productivity_impact(db, user)


@router.get("/insights/environments", response_model=EnvironmentComparisonOut)
def insights_environments(db=Depends(get_db), user=Depends(get_current_user)):
    return get_environment_comparison(db, user)


@router.get("/insights/top-resources", response_model=list[TopResourceOut])
def insights_top_resources(
    limit: int = Query(default=10, ge=1, le=100),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    return get_top_resources(db, user, limit=limit)
