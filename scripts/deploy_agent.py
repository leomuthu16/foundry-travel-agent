"""Create a new version of the agent from the files in agent/.

Usage:
    python scripts/deploy_agent.py

The agent definition (model, instructions, tools) lives in Git, so every change is
reviewed and traceable. Each run creates a new agent version; old versions stay
available for rollback.
"""
import os
import subprocess

from azure.ai.projects.models import (
    AutoCodeInterpreterToolParam,
    CodeInterpreterTool,
    FileSearchTool,
    PromptAgentDefinition,
)

from foundry_common import ROOT, get_project, load_config


def git_commit() -> str:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:12]
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "local"


def main() -> None:
    config = load_config()
    instructions = (ROOT / config["instructions_file"]).read_text(encoding="utf-8").strip()

    tools = []
    file_search = config.get("file_search") or {}
    vector_store_id = file_search.get("vector_store_id", "")
    if vector_store_id and not vector_store_id.startswith("REPLACE"):
        tools.append(FileSearchTool(vector_store_ids=[vector_store_id],
                                    max_num_results=file_search.get("max_num_results", 5)))
    else:
        raise SystemExit("Set file_search.vector_store_id in agent/agent.config.json "
                         "(or the VECTOR_STORE_ID environment variable).")
    if config.get("code_interpreter"):
        tools.append(CodeInterpreterTool(container=AutoCodeInterpreterToolParam()))

    project = get_project()
    agent = project.agents.create_version(
        agent_name=config["agent_name"],
        definition=PromptAgentDefinition(
            model=config["model"],
            instructions=instructions,
            tools=tools,
        ),
        description="Contoso Travel & Expense Policy Assistant",
        metadata={"git_commit": git_commit(), "deployed_by": os.getenv("GITHUB_ACTOR", "local")},
    )

    print(f"Deployed agent '{agent.name}' version {agent.version} (commit {git_commit()})")

    # Pass the version to the next pipeline step
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"agent_version={agent.version}\n")


if __name__ == "__main__":
    main()
