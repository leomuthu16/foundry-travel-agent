"""Create (or add a version of) the blog reader agent with the Azure AI Search tool.

    python scripts/create_agent.py

Needs an Azure AI Search connection in the Foundry project (guide step R5).
Set SEARCH_CONNECTION_NAME if the project has more than one.
"""
import os
import sys

from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchTool,
    AzureAISearchToolResource,
    ConnectionType,
    PromptAgentDefinition,
)

from common import ROOT, get_project, load_config, set_output


def main() -> None:
    cfg = load_config()
    project = get_project()

    name = os.getenv("SEARCH_CONNECTION_NAME")
    if name:
        connection = project.connections.get(name)
    else:
        found = list(project.connections.list(connection_type=ConnectionType.AZURE_AI_SEARCH))
        if not found:
            sys.exit("No Azure AI Search connection in this project. Add one first (guide step R5).")
        connection = found[0]
    print(f"Using search connection '{connection.name}'")

    tool = AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[AISearchIndexResource(
        project_connection_id=connection.id,
        index_name=cfg["index_name"],
        query_type=cfg["search_query_type"],
        top_k=cfg["top_k"],
    )]))
    agent = project.agents.create_version(
        agent_name=cfg["agent_name"],
        definition=PromptAgentDefinition(
            model=cfg["model"],
            instructions=(ROOT / cfg["instructions_file"]).read_text(encoding="utf-8").strip(),
            tools=[tool],
        ),
        description="Reader assistant for the Contoso DataHub blog (RAG prototype)",
    )
    print(f"Agent '{agent.name}' version {agent.version} ready (index: {cfg['index_name']}, query type: {cfg['search_query_type']})")
    set_output("agent_version", agent.version)


if __name__ == "__main__":
    main()
