"""Command-line entry point: salesops-agent ask "question"."""

import argparse
import sys

from dotenv import load_dotenv

from salesops_agent.agent.runner import run_question
from salesops_agent.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(prog="salesops-agent", description="UdaCenture SalesOps agent")
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="ask the agent a question")
    ask.add_argument("question", help="the question to ask")
    ask.add_argument(
        "--approval",
        choices=["approve", "reject"],
        help="decision for any action that needs human approval, such as sending an email",
    )
    args = parser.parse_args()

    load_dotenv(override=True)
    result = run_question(load_config(), args.question, approval=args.approval)

    if result.error:
        print(f"Run {result.run_id} failed: {result.error}", file=sys.stderr)
        return 1
    print(result.answer)
    if result.hitl and result.hitl["approval_requested"]:
        decision = result.hitl["decision"] or "none (pending)"
        print(f"Approval requested for {result.hitl['action']}; decision: {decision}", file=sys.stderr)
    if result.guardrail:
        print(f"Blocked by guardrail: {result.guardrail['reason']}", file=sys.stderr)
    print(f"Run ID: {result.run_id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
