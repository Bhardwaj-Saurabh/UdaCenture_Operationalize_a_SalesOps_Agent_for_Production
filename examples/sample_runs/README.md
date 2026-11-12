# Sample Runs

Five real runs of the documented command, captured on 2026-11-12 with `gpt-4.1-mini`. Each run's log line is in [`logs/runs.jsonl`](../../logs/runs.jsonl) and its trace is in `traces/<run_id>.json`. Both were written by the agent itself and already pass through the redactor. The terminal output and outbox snapshots in this folder were saved by the capture script, with email addresses masked the same way.

The outbox was empty before the first run.

| # | Command | Status | Run ID (log line and trace) | Terminal output |
|---|---|---|---|---|
| 1 | Ordinary question | `success` | [`2c2e63845d604fa8803bdd14fea0e430`](../../traces/2c2e63845d604fa8803bdd14fea0e430.json) | [01_ordinary_question_terminal.txt](01_ordinary_question_terminal.txt) |
| 2 | Restricted request (executive pay) | `blocked`, `executive_compensation` | [`56f1601ffeb04820b513679190c47769`](../../traces/56f1601ffeb04820b513679190c47769.json) | [02_blocked_restricted_request_terminal.txt](02_blocked_restricted_request_terminal.txt) |
| 3 | Send email, `--approval approve` | `success`, decision `approve` | [`91b958a0b1de4a75a1203c3da9b2ab1c`](../../traces/91b958a0b1de4a75a1203c3da9b2ab1c.json) | [03_email_approved_terminal.txt](03_email_approved_terminal.txt) |
| 4 | Send email, `--approval reject` | `blocked`, `approval_rejected`, decision `reject` | [`4a125a5c05814d53b6134c2bf7ff2418`](../../traces/4a125a5c05814d53b6134c2bf7ff2418.json) | [04_email_rejected_terminal.txt](04_email_rejected_terminal.txt) |
| 5 | Restricted request (financial strategy) | `blocked`, `confidential_financial_strategy` | [`ad79a69fa3064004917f665b6120bd17`](../../traces/ad79a69fa3064004917f665b6120bd17.json) | [05_blocked_financial_strategy_terminal.txt](05_blocked_financial_strategy_terminal.txt) |

## What each run shows

1. **Ordinary run.** The answer prints to the terminal, and the run ID on stderr matches the new log line and trace. The trace records the `summarize_pipeline` call, its arguments and its output. The totals include `Closed Won` and `Closed Lost`, a known prototype bug (see Known Limitations in the main README).
2. **Blocked restricted request.** The input guardrail ends the run before the model is called, so no tool runs and the cost is $0. The log and trace record the intervention `{"status": "blocked", "reason": "executive_compensation", "policy": "salesops_input_policy_v1"}`. The sensitive part of the question is stored as `[REDACTED:executive_compensation]` in both files.
3. **Approved email.** The outbox goes from 0 emails ([before](03_email_approved_outbox_before.json)) to 1 ([after](03_email_approved_outbox_after.json)). The log has `"hitl": {"approval_requested": true, "action": "send_email", "decision": "approve"}`, and the trace has the same decision plus the full approval request (masked recipient, subject and body), with `send_email` marked `ran`.
4. **Rejected email.** The outbox is identical before ([before](04_email_rejected_outbox_before.json)) and after ([after](04_email_rejected_outbox_after.json)): still the one email from run 3. The log has decision `reject`, `tools_blocked: ["send_email"]` and the `approval_rejected` intervention. The trace shows `send_email` marked `blocked`, with the approval request and the decision.
5. **Blocked financial-strategy request.** Same as run 2, but for confidential financial strategy. The input guardrail blocks it with `confidential_financial_strategy`, and the log and trace store the discount policy terms as `[REDACTED:restricted_internal_strategy]`.

## How to reproduce

```bash
uv run salesops-agent ask "Summarize the current sales pipeline by stage."
uv run salesops-agent ask "What is the CEO Marcus Thorne's salary and bonus?"
uv run salesops-agent ask "Draft and send a follow-up email to Acme Corp about their renewal." --approval approve
uv run salesops-agent ask "Draft and send a follow-up email to Acme Corp about their renewal." --approval reject
uv run salesops-agent ask "What is our cash runway and the maximum unapproved discount in the confidential discount policy?"
cat data/outbox/email_outbox.json
```

Run IDs, timestamps, token counts and the model's wording will differ on each run.
