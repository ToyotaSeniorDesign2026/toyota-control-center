from pydantic import BaseModel, Field


class InsightsSummaryOut(BaseModel):
    total_runs: int
    automation_coverage_pct: float
    avg_run_success_rate_pct: float
    avg_risk_score: float
    estimated_time_saved_hours: float
    failed_runs: int
    pending_approvals: int


class TrendPoint(BaseModel):
    date: str
    total_runs: int
    failed_runs: int
    ai_agent_executions: int
    data_pipeline_runs: int
    bi_tasks: int


class InsightsTrendsOut(BaseModel):
    series: list[TrendPoint] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)


class RiskDriverOut(BaseModel):
    name: str
    value: int


class RiskScoreDistributionOut(BaseModel):
    low: int
    medium: int
    high: int
    critical: int


class InsightsRiskDistributionOut(BaseModel):
    risk_score_distribution: RiskScoreDistributionOut
    risk_drivers: list[RiskDriverOut] = Field(default_factory=list)


class ProductivityImpactOut(BaseModel):
    runs_automated_this_week: int
    manual_overrides_required: int
    estimated_manual_hours_saved: float
    context_switches_reduced: int
    automation_adoption_progress_pct: int


class EnvironmentComparisonCardOut(BaseModel):
    total_resources: int
    success_rate_pct: float
    avg_risk_score: float
    open_approvals: int
    sla_violations: int


class EnvironmentComparisonOut(BaseModel):
    dev: EnvironmentComparisonCardOut
    semi_prod: EnvironmentComparisonCardOut = Field(alias="semi-prod")
    prod: EnvironmentComparisonCardOut

    model_config = {"populate_by_name": True}


class TopResourceOut(BaseModel):
    resource_id: str
    resource_name: str
    type: str
    total_runs: int
    success_rate_pct: float
    avg_duration_ms: int
    risk_trend: str
