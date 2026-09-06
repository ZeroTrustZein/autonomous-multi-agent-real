# Autonomous Multi-Agent Real Estate Deal Underwriting & Cash Flow Simulation Workflow Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

An autonomous multi-agent underwriting and cash flow simulation workflow engine for real estate investments. Built in Python with Pydantic v2, NumPy vectorized Monte Carlo simulation, and an event-driven agent pipeline.

## System Architecture

The engine coordinates specialized underwriting agents in an orchestrated workflow DAG:

```
                          [ Property Deal Submission ]
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │       Acquisition Agent       │
                       │ - Intake & Unit Mix Modeling  │
                       │ - Initial Basis & Screening   │
                       └───────────────┬───────────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
       ┌───────────────────────────────┐ ┌───────────────────────────────┐
       │      Market Comps Agent       │ │      Debt Financing Agent     │
       │ - Rent Comps & Loss-to-Lease  │ │ - DSCR, LTV & Debt Yield      │
       │ - Market Cap Rates & Vacancy  │ │ - Amortization & Loan Sizing  │
       └──────────────┬────────────────┘ └──────────────┬────────────────┘
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │     Cash Flow Simulation      │
                       │ - Multi-Year Pro-Forma (NOI)  │
                       │ - BTCF, Debt Service & Exit   │
                       │ - Levered / Unlevered IRR     │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │    Risk & Monte Carlo Agent   │
                       │ - Vectorized Stochastic Sim   │
                       │ - Cap Rate / Rent Sensitivities│
                       │ - VaR, Quantiles (P10/50/90)  │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │ Investment Committee Synthesis│
                       │ - Deal Score & Recommendations│
                       │ - Executive Underwriting Memo │
                       └───────────────────────────────┘
```

## Quickstart

```bash
# Install editable package
pip install -e .

# Run CLI workflow on benchmark deal
autonomous-multi-agent-real underwrite --deal-id austin-multifamily

# Run Monte Carlo cash flow simulation
autonomous-multi-agent-real simulate --deal-id austin-multifamily --iterations 2000
```
