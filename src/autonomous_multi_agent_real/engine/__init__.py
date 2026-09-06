"""Core workflow engine, financial math, and Monte Carlo simulation."""

from autonomous_multi_agent_real.engine.financial import (
    calculate_cap_rate,
    calculate_debt_yield,
    calculate_dscr,
    calculate_equity_multiple,
    calculate_exit_sale_proceeds,
    calculate_irr,
    calculate_loan_amortization_schedule,
    calculate_monthly_mortgage_payment,
    calculate_npv,
)
from autonomous_multi_agent_real.engine.monte_carlo import MonteCarloEngine
from autonomous_multi_agent_real.engine.optimizer import DealOptimizer
from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine
from autonomous_multi_agent_real.engine.state import DealWorkflowContext
from autonomous_multi_agent_real.engine.tax import TaxEngine
from autonomous_multi_agent_real.engine.waterfall import (
    WaterfallEngine,
    get_default_waterfall_structure,
)
from autonomous_multi_agent_real.engine.workflow import DealPipeline

__all__ = [
    "DealPipeline",
    "MonteCarloEngine",
    "DealWorkflowContext",
    "WaterfallEngine",
    "get_default_waterfall_structure",
    "SensitivityEngine",
    "TaxEngine",
    "DealOptimizer",
    "calculate_monthly_mortgage_payment",
    "calculate_loan_amortization_schedule",
    "calculate_irr",
    "calculate_npv",
    "calculate_equity_multiple",
    "calculate_dscr",
    "calculate_debt_yield",
    "calculate_cap_rate",
    "calculate_exit_sale_proceeds",
]
