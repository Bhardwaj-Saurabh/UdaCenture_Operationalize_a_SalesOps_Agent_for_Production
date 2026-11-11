# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This is a Udacity project: turn a prototype SalesOps agent into a production-ready Python app. Steps 1-3 and 5.1-5.5 are done, and Step 4 lacks estimated cost: the notebook is refactored into a Python package that keeps the prototype's behavior, including its unsafe tools and known bugs. **Update this file as the project takes shape, especially the commands and architecture sections.**

- `README.md`: the full project brief (Steps 1-8), not yet the project's own README, plus the `## Sandboxed Execution` and `## Human-in-the-Loop Workflow` sections added before `## License`. Read the relevant step before implementing it.
- `starter/README.md`: the list of what the final student README must contain.
- `starter/`: the original notebook and its data, kept as reference. `data/` is what the app reads.
- `src/salesops_agent/`: the package. `agent/factory.py` builds the agent, `tools/registry.py` selects tools from the config, and `data_access/crm_store.py` holds CRM lookups.
- `src/salesops_agent/cli.py` is the entry point and `agent/runner.py` runs one question. Each run appends to `logs/runs.jsonl` and writes `traces/<run_id>.json`. Both are basic until Step 6, and traces omit tool outputs until redaction exists.
- `config/guardrails/`: versioned input, tool, and output policies, selected in the config. `src/salesops_agent/guardrails/` holds the filters and middleware. `input.py` ends a run before the model is called. `tool.py` checks each tool call before it runs, and any block ends the run. `output.py` replaces a restricted final answer with a refusal (block, not redact), and checks `send_email` content before the approval check.
- Middleware order in `agent/factory.py` matters: the output guardrail must wrap tool calls outside the tool guardrail. Refusals written by a guardrail carry `GUARDRAIL_KEY` or `REFUSAL_KEY` so the output check skips them.
- A new tool must be added to `allowed_tools` in the tool policy as well as the config, because the policy denies by default.
- `src/salesops_agent/sandbox.py` runs `run_crm_analysis` code in a separate process: an `ast` check first, then safe built-ins, approved CRM tables only, a timeout, and capped output. The tool guardrail runs the same check (`unsafe_code`). It must be started from a real file, because a `spawn` child cannot re-import a script piped through stdin.
- Approval gate: `tool.py` calls `interrupt()` for `approval_required_tools` (in `tool_policy_v2.yaml`) before the tool runs. `agent/runner.py` builds the agent with an `InMemorySaver` and resumes with `Command(resume={"type": ...})`. Run statuses are `success`, `blocked`, `failed`, and `awaiting_approval`. Each traced tool call has an `outcome` of `ran`, `blocked`, or `pending`.
- `src/salesops_agent/reporting/`: a placeholder with no code yet.
- `config/agent.yaml`: config version, model, prompt version, tool and schema versions, enabled tools, and paths. Secrets stay in `.env` (see `.env.example`).
- `prompts/<name>/<version>.md`: versioned prompts, selected in the config.
- `schemas/v1.py` and `TOOLS_VERSION` in `tools/__init__.py` (both under `src/salesops_agent/`): tool input schemas and the tool version. `tools/registry.py` refuses to build tools if the config pins different versions, so bump both together.
- `data/crm/` and `data/restricted/`: approved CRM data and internal HR/financial data, kept apart. `CrmStore` reads only `data/crm/`.

## Commands

```bash
uv sync
uv run salesops-agent ask "Summarize the current sales pipeline by stage."
uv run salesops-agent ask "Draft and send a follow-up email to Acme Corp" --approval approve   # or reject
```

Run the evaluation suite and the sandbox tests with `uv run pytest`, or one task with `uv run pytest -k T004`. It makes real model calls and writes `reports/evaluation_report.json`. There is no linter, and the notebook kernel is not installed in `.venv`.

Tasks are in `data/evaluation/golden_tasks.csv`, where `;` separates required items and `|` separates alternatives. Scoring is in `src/salesops_agent/evaluation/suite.py`. Tasks with `scripted_tool` or `scripted_answer` use a fake model that returns exactly that, so they are repeatable and make no API calls. T004 (the model miscounts) and T005 (the `difflib` crash) are known failures that were kept on purpose. `expected_status` accepts alternatives with `|`, and the `approval` column passes a decision. Approved email tasks write to the gitignored outbox on every run. T022 allows `blocked|success`, because the live model sometimes asks a clarifying question instead of trying the HR tool. Either way the HR tool must not run. Running a subset with `-k` overwrites the report with only those tasks, so run the full suite before committing the report. Estimated cost is not reported yet, though the brief requires it.

The brief specifies these commands, which do not exist yet:

```bash
uv run generate-monitoring-report   # Step 7, writes reports/monitoring_report.md
git log --oneline --decorate --graph --all > GITLOG.txt
```

The agent uses `ChatOpenAI` and reads `OPENAI_API_KEY` and `OPENAI_API_BASE` from the environment or `.env`, with `.env` taking priority.

## Target architecture

The code must keep agent creation, prompts, tools, configuration, evaluation, logging, tracing, and reporting separate.

All five controls exist. All prototype tools stay enabled so the tool guardrail can be shown blocking them. Once built, every run must pass through these controls, each enforced in code rather than left to the model to refuse:

1. **Input guardrails** run before the request reaches the agent. They cover HR data, executive compensation, terminations/PIPs, M&A, layoffs, confidential strategy, and prompt injection.
2. **Tool/action guardrails** inspect each proposed tool call before it executes. A blocked call returns an explicit, logged result such as `{"status": "blocked", "reason": "restricted_internal_data", "policy": "salesops_data_access_policy"}`.
3. **HITL gate** on `send_email`, driven by `--approval approve|reject`. A rejected email must never reach the outbox. The decision is logged, and the trace must show that approval was requested.
4. **Sandboxed analysis tool** works over approved CRM data only: no unrestricted `eval`/`exec`, no network, restricted imports, a timeout, controlled input and output, and no HR or financial data.
5. **Output guardrails** check the final response. They also check drafted emails for invented discounts, legal commitments, and acquisition details.

Each run writes one record to a JSONL log (e.g. `logs/runs.jsonl`) and one redacted trace (e.g. `traces/<run_id>.json`). The monitoring report aggregates those logs. The evaluation report must cover the eight scenarios listed in brief section 5.6.

## Data model and pitfalls

- An account is any tracked organization. Only accounts with at least one `Closed Won` opportunity are customers (27 of 109), and only customers have support tickets and product usage.
- **Sensitive subjects overlap with legitimate CRM data, so naive keyword or name blocking will break safe questions.** Acme Corp (A001) is both a normal customer and the confidential M&A target. Maya Chen and Rafael Costa are CRM account or activity owners as well as HR records. "Acme Corp's renewal" must work while "Are we acquiring Acme Corp?" is blocked.
- Input policy patterns must match intent, never a name alone, and need checking against safe lookalike questions (see T014-T016 in the golden tasks).
- `internal_hr_data.json` and `internal_financial_data.json` hold the restricted data. The confidential discount policy is in the financial file, so it also matters for email drafting.
- The CRM files contain no embedded injection strings or restricted terms as of this writing, so injection evals have to supply their own attack text.

Prototype behavior carried into `src/` unchanged, still to be fixed:

- `find_account_by_name` calls `difflib` without importing it, so any account name with no match raises `NameError` instead of returning "No account found".
- The partial-match step in `find_account_by_name` returns the first match in either direction, so it can resolve to the wrong account. For example, "a" resolves to Acme Corp.
- `summarize_pipeline` includes `Closed Won` and `Closed Lost` in its totals.
- The system prompt still says "You may use internal tools if needed."

`send_email` writes to `data/outbox/email_outbox.json`, which is gitignored. The notebook writes to `starter/data/email_outbox.json`, which is tracked, so running the notebook dirties the repo.

## Project requirements that are easy to miss

- `GITLOG.txt` must be generated from real history, and regenerated before submission because it goes stale with each commit. The brief expects distinct commits for: project structure, prompts/config, tool refactor, evaluation suite, guardrails, sandbox, HITL, logging/tracing/reporting, and docs.
- The final README must have these exact section headings: `## Prototype Review`, `## Sandboxed Execution`, `## Human-in-the-Loop Workflow`, `## Logging and Tracing`, `## Monitoring Report`.
- Monitoring stays local. Grafana, LangSmith, Langfuse, and MLflow are not needed.
