# Monitoring Report

Generated 2026-11-11T22:39:39+00:00 from `/Users/saurabhbhardwaj/Documents/UdaCenture/logs/runs.jsonl`. Covers 292 runs from 2026-11-04T14:46:04 to 2026-11-11T22:34:27 UTC. 43 of them have a task ID (evaluation suite runs, or CLI runs with `--task-id`).

## Highlights

- 12 runs failed (4.1%). The most common cause (11 runs) was `NameError: name 'difflib' is not defined`.
- Guardrails stopped 170 runs (58.2%). The most frequent reason was `restricted_internal_data` (22). A high share is expected when evaluation runs include many attack scenarios.
- Average latency (1.16s) is pulled down by blocked runs that never call the model; answered runs averaged 3.03s.
- 22 runs asked for approval: 8 approved, 7 rejected, 7 left without a decision.
- Cost covers 47 of 292 runs; the rest were logged before cost tracking existed.

## Summary

| Metric | Value |
|---|---|
| Total runs | 292 |
| Success rate | 32.9% |
| Failure rate | 4.1% |
| Average latency | 1.16s |
| Estimated total cost | $0.0175 |
| Estimated average cost per run | $0.000372 |
| Guardrail blocks | 170 |
| HITL approvals | 8 |
| HITL rejections | 7 |

## Outcomes

Every run ends in exactly one status. A block is the system working as intended, so it is counted separately from a failure.

| Status | Runs | Share |
|---|---|---|
| Answered | 96 | 32.9% |
| Blocked (guardrail or rejected approval) | 177 | 60.6% |
| Failed (error) | 12 | 4.1% |
| Awaiting approval | 7 | 2.4% |

## Latency

| Measure | Seconds |
|---|---|
| Average (all runs) | 1.16 |
| Average (answered runs) | 3.03 |
| Median | 0.01 |
| 95th percentile | 3.86 |
| Slowest | 17.00 |

## Cost

Estimated from token counts and the rates in `config/agent.yaml`. Covers 47 of 292 runs that recorded token usage.

| Measure | Value |
|---|---|
| Estimated total cost | $0.0175 |
| Average per run | $0.000372 |
| Average per run that called the model | $0.000971 |
| Input tokens | 35,540 |
| Output tokens | 2,034 |

## Tool calls

`Ran` counts calls that executed. `Blocked` counts calls the model proposed that a guardrail or reviewer stopped.

| Tool | Ran | Blocked |
|---|---|---|
| `lookup_account_context` | 51 | 0 |
| `send_email` | 9 | 26 |
| `run_crm_analysis` | 15 | 19 |
| `lookup_account` | 20 | 8 |
| `draft_email` | 24 | 0 |
| `list_open_opportunities` | 14 | 0 |
| `lookup_internal_hr_data` | 0 | 12 |
| `lookup_internal_financial_data` | 0 | 10 |
| `summarize_pipeline` | 9 | 0 |
| `execute_python` | 0 | 8 |
| `finalize_email` | 0 | 4 |

## Guardrail blocks

170 runs were stopped by a guardrail. Reviewer rejections are counted under HITL instead.

| Layer | Blocks |
|---|---|
| tool | 72 |
| input | 53 |
| output | 45 |

| Reason | Blocks |
|---|---|
| `restricted_internal_data` | 22 |
| `unsafe_code` | 18 |
| `executive_compensation` | 17 |
| `prompt_injection` | 14 |
| `confidential_m_and_a` | 13 |
| `unsafe_email_claims` | 13 |
| `layoff_plans` | 12 |
| `tool_not_allowed` | 12 |
| `approval_required` | 11 |
| `out_of_scope_request` | 9 |
| `restricted_hr_data` | 7 |
| `confidential_financial_strategy` | 7 |
| `employee_performance_or_termination` | 5 |
| `restricted_internal_strategy` | 5 |
| `raw_sensitive_fields` | 5 |

## Human-in-the-loop

| Measure | Runs |
|---|---|
| Approval requested | 22 |
| Approved | 8 |
| Rejected | 7 |
| Pending (no decision given) | 7 |

## Common failure reasons

| Reason | Runs |
|---|---|
| `NameError: name 'difflib' is not defined` | 11 |
| `OpenAIConnectionError: Connection error.` | 1 |

## Data notes

- 245 runs were logged in an older format, before cost and redaction were added. They count toward outcomes, latency, tools, and guardrails, but not cost.
- 0 unreadable log lines were skipped.
