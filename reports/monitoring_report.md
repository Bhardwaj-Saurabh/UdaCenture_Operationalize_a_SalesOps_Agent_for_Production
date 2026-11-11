# Monitoring Report

Generated 2026-11-11T22:47:37+00:00 from `/Users/saurabhbhardwaj/Documents/UdaCenture/logs/runs.jsonl`. Covers 42 runs from 2026-11-11T22:46:36 to 2026-11-11T22:47:15 UTC. 42 of them have a task ID (evaluation suite runs, or CLI runs with `--task-id`).

## Highlights

- 1 run failed (2.4%). The most common cause (1 run) was `NameError: name 'difflib' is not defined`.
- Guardrails stopped 24 runs (57.1%). The most frequent reason was `unsafe_code` (4). A high share is expected when evaluation runs include many attack scenarios.
- Average latency (0.92s) is pulled down by blocked runs that never call the model; answered runs averaged 2.51s.
- 6 runs asked for approval: 2 approved, 2 rejected, 2 left without a decision.
- Runs that call the model average $0.000971, within the $0.05 cost threshold.

## Summary

| Metric | Value |
|---|---|
| Total runs | 42 |
| Success rate | 31.0% |
| Failure rate | 2.4% |
| Average latency | 0.92s |
| Estimated total cost | $0.0146 |
| Estimated average cost per run | $0.000347 |
| Guardrail blocks | 24 |
| HITL approvals | 2 |
| HITL rejections | 2 |

## Outcomes

Every run ends in exactly one status. A block is the system working as intended, so it is counted separately from a failure.

| Status | Runs | Share |
|---|---|---|
| Answered | 13 | 31.0% |
| Blocked (guardrail or rejected approval) | 26 | 61.9% |
| Failed (error) | 1 | 2.4% |
| Awaiting approval | 2 | 4.8% |

## Latency

| Measure | Seconds |
|---|---|
| Average (all runs) | 0.92 |
| Average (answered runs) | 2.51 |
| Median | 0.01 |
| 95th percentile | 2.98 |
| Slowest | 4.03 |

## Cost

Estimated from token counts and the rates in `config/agent.yaml`. Covers 42 of 42 runs that recorded token usage.

| Measure | Value |
|---|---|
| Estimated total cost | $0.0146 |
| Average per run | $0.000347 |
| Average per run that called the model | $0.000971 |
| Input tokens | 29,689 |
| Output tokens | 1,680 |

## Tool calls

`Ran` counts calls that executed. `Blocked` counts calls the model proposed that a guardrail or reviewer stopped.

| Tool | Ran | Blocked |
|---|---|---|
| `run_crm_analysis` | 3 | 4 |
| `send_email` | 2 | 3 |
| `draft_email` | 4 | 0 |
| `lookup_account_context` | 4 | 0 |
| `lookup_account` | 2 | 1 |
| `lookup_internal_financial_data` | 0 | 1 |
| `list_open_opportunities` | 1 | 0 |
| `finalize_email` | 0 | 1 |
| `summarize_pipeline` | 1 | 0 |
| `lookup_internal_hr_data` | 0 | 1 |
| `execute_python` | 0 | 1 |

## Guardrail blocks

24 runs were stopped by a guardrail. Reviewer rejections are counted under HITL instead.

| Layer | Blocks |
|---|---|
| tool | 9 |
| output | 8 |
| input | 7 |

| Reason | Blocks |
|---|---|
| `unsafe_code` | 4 |
| `prompt_injection` | 2 |
| `executive_compensation` | 2 |
| `confidential_m_and_a` | 2 |
| `layoff_plans` | 2 |
| `restricted_internal_data` | 2 |
| `tool_not_allowed` | 2 |
| `unsafe_email_claims` | 2 |
| `restricted_hr_data` | 1 |
| `confidential_financial_strategy` | 1 |
| `out_of_scope_request` | 1 |
| `employee_performance_or_termination` | 1 |
| `restricted_internal_strategy` | 1 |
| `raw_sensitive_fields` | 1 |

## Human-in-the-loop

| Measure | Runs |
|---|---|
| Approval requested | 6 |
| Approved | 2 |
| Rejected | 2 |
| Pending (no decision given) | 2 |

## Common failure reasons

| Reason | Runs |
|---|---|
| `NameError: name 'difflib' is not defined` | 1 |

## Data notes

- 0 runs were logged in an older format, before cost and redaction were added. They count toward outcomes, latency, tools, and guardrails, but not cost.
- 0 unreadable log lines were skipped.
