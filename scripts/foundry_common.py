"""Shared helpers for deploying, testing and chatting with the Foundry agent."""
import json
import os
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """Read agent/agent.config.json. Environment variables override it, so each
    pipeline environment (dev, prod) can point to its own project and vector store."""
    config = json.loads((ROOT / "agent" / "agent.config.json").read_text(encoding="utf-8"))
    if os.getenv("AGENT_NAME"):
        config["agent_name"] = os.environ["AGENT_NAME"]
    if os.getenv("MODEL_DEPLOYMENT"):
        config["model"] = os.environ["MODEL_DEPLOYMENT"]
    if os.getenv("VECTOR_STORE_ID"):
        config["file_search"]["vector_store_id"] = os.environ["VECTOR_STORE_ID"]
    claims = config.setdefault("claims_api", {"enabled": False})
    if os.getenv("CLAIMS_API_URL"):  # setting the URL per environment also switches the tool on
        claims["base_url"] = os.environ["CLAIMS_API_URL"]
        claims["enabled"] = True
    return config


def get_project() -> AIProjectClient:
    """Connect to the Foundry project. Sign-in comes from DefaultAzureCredential:
    'az login' on your laptop, or the azure/login step in GitHub Actions. No API keys."""
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        sys.exit("Set FOUNDRY_PROJECT_ENDPOINT to your project endpoint "
                 "(https://<resource>.services.ai.azure.com/api/projects/<project>).")
    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential(), allow_preview=True)


def ask(project: AIProjectClient, agent_name: str, question: str,
        version: str | None = None, conversation_id: str | None = None):
    """Send one message to the agent and return the OpenAI Responses object.
    Passing a version lets the pipeline test the exact version it just deployed."""
    reference = {"type": "agent_reference", "name": agent_name}
    if version:
        reference["version"] = str(version)
    kwargs = {"input": question, "extra_body": {"agent_reference": reference}}
    if conversation_id:
        kwargs["conversation"] = conversation_id
    try:
        return project.get_openai_client().responses.create(**kwargs)
    except Exception as first_error:  # SDK versions differ; fall back to the agent-bound client
        if version:
            raise
        try:
            client = project.get_openai_client(agent_name=agent_name)
            fallback = {"input": question}
            if conversation_id:
                fallback["conversation"] = conversation_id
            return client.responses.create(**fallback)
        except Exception:
            raise first_error


def tools_used(response) -> list[str]:
    """List the tools the agent called, e.g. ['file_search', 'code_interpreter']."""
    used = []
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", "") or ""
        if item_type.endswith("_call"):
            name = item_type[: -len("_call")]
            if name not in used:
                used.append(name)
    return used


def token_usage(response) -> int | None:
    usage = getattr(response, "usage", None)
    return getattr(usage, "total_tokens", None) if usage else None
