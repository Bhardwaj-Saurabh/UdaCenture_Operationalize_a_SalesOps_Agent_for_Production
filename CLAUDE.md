# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This is a Udacity project: turn a prototype SalesOps agent into a production-ready Python app. So far the repo holds only the brief and the starter code. There is no `src/`, `pyproject.toml`, tests, or `.gitignore` yet. **Update this file as the project takes shape, especially the commands and architecture sections.**

- `README.md`: the full project brief (Steps 1-8). Read the relevant step before implementing it.
- `starter/README.md`: the list of what the final student README must contain.
- `starter/project_starter.ipynb`: the prototype. It is reference material; the brief says not to build the final project in it.
- `starter/data/`: mock CRM and internal JSON data.

## Commands

The brief specifies these commands, but none of them work until Step 1 is done. `uv` is the required tool for installing and running.

```bash
uv sync
uv run salesops-agent ask "Summarize the account risk for TechStart Inc."
uv run salesops-agent ask "Draft and send a follow-up email to Acme Corp" --approval approve   # or reject
uv run evaluate                     # or: uv run pytest; writes reports/evaluation_report.{md,csv,json}
uv run generate-monitoring-report   # writes reports/monitoring_report.md
git log --oneline --decorate --graph --all > GITLOG.txt
```

The prototype needs `OPENAI_API_KEY` (from the environment or `.env`) and uses `openai:gpt-4o-mini` through LangChain's `create_agent`. Its notebook kernel is Python 3.12. It must run from `starter/`, because its data paths are relative to the working directory.

## Target architecture

The brief requires these top-level items: `src/`, `data/`, `logs/`, `traces/`, `reports/`, `pyproject.toml`, `uv.lock`, `README.md`, `.python-version`, `.gitignore`, and `GITLOG.txt`. The code must keep agent creation, prompts, tools, configuration, evaluation, logging, tracing, and reporting separate.

Every run passes through these controls, and each must be enforced in code rather than left to the model to refuse:

1. **Input guardrails** run before the request reaches the agent. They cover HR data, executive compensation, terminations/PIPs, M&A, layoffs, confidential strategy, and prompt injection.
2. **Tool/action guardrails** inspect each proposed tool call before it executes. A blocked call returns an explicit, logged result such as `{"status": "blocked", "reason": "restricted_internal_data", "policy": "salesops_data_access_policy"}`.
3. **HITL gate** on `send_email`, driven by `--approval approve|reject`. A rejected email must never reach the outbox. The decision is logged, and the trace must show that approval was requested.
4. **Sandboxed analysis tool** works over approved CRM data only: no unrestricted `eval`/`exec`, no network, restricted imports, a timeout, controlled input and output, and no HR or financial data.
5. **Output guardrails** check the final response. They also check drafted emails for invented discounts, legal commitments, and acquisition details.

Each run writes one record to a JSONL log (e.g. `logs/runs.jsonl`) and one redacted trace (e.g. `traces/<run_id>.json`). The monitoring report aggregates those logs. The evaluation report must cover the eight scenarios listed in brief section 5.6.

## Data model and pitfalls

- An account is any tracked organization. Only accounts with at least one `Closed Won` opportunity are customers (27 of 109), and only customers have support tickets and product usage.
- **Sensitive subjects overlap with legitimate CRM data, so naive keyword or name blocking will break safe questions.** Acme Corp (A001) is both a normal customer and the confidential M&A target. Maya Chen and Rafael Costa are CRM account or activity owners as well as HR records. "Acme Corp's renewal" must work while "Are we acquiring Acme Corp?" is blocked.
- `internal_hr_data.json` and `internal_financial_data.json` hold the restricted data. The confidential discount policy is in the financial file, so it also matters for email drafting.
- The CRM files contain no embedded injection strings or restricted terms as of this writing, so injection evals have to supply their own attack text.

Prototype behavior to fix rather than carry over:

- `find_account_by_name` calls `difflib`, but the notebook never imports it, so the fuzzy fallback raises `NameError` when reached.
- `send_email` appends to `data/email_outbox.json`, a tracked file that already has one sent message. Running the agent or evals against it dirties the repo.
- The partial-match step in `find_account_by_name` returns the first match in either direction, so it can resolve to the wrong account.
- `summarize_pipeline` includes `Closed Won` and `Closed Lost` in its totals.

## Project requirements that are easy to miss

- `GITLOG.txt` must be generated from real history. The brief expects distinct commits for: project structure, prompts/config, tool refactor, evaluation suite, guardrails, sandbox, HITL, logging/tracing/reporting, and docs.
- The final README must have these exact section headings: `## Prototype Review`, `## Sandboxed Execution`, `## Human-in-the-Loop Workflow`, `## Logging and Tracing`, `## Monitoring Report`.
- Monitoring stays local. Grafana, LangSmith, Langfuse, and MLflow are not needed.
