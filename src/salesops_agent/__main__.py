"""Run one question through the agent: uv run python -m salesops_agent "question"."""

import sys

from dotenv import load_dotenv

from salesops_agent.agent.factory import create_salesops_agent
from salesops_agent.config import load_config


def main() -> None:
    load_dotenv(override=True)
    agent = create_salesops_agent(load_config())
    response = agent.invoke({"messages": [{"role": "user", "content": sys.argv[1]}]})
    print(response["messages"][-1].content)


if __name__ == "__main__":
    main()
