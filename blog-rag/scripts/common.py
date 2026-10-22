"""Shared helpers for the blog RAG prototype."""
import json
import os
import sys
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """rag.config.json, with INDEX_NAME and AGENT_NAME overridable per environment (dev / prod)."""
    cfg = json.loads((ROOT / "rag.config.json").read_text(encoding="utf-8"))
    for key, env in (("index_name", "INDEX_NAME"), ("agent_name", "AGENT_NAME")):
        if os.getenv(env, "").strip():
            cfg[key] = os.getenv(env).strip()
    return cfg


def need(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        sys.exit(f"Set the environment variable {name} (see the guide, step R3).")
    return value.rstrip("/")


def search_credential():
    """Admin key if SEARCH_ADMIN_KEY is set (simplest for practice), otherwise Entra ID sign-in."""
    key = os.getenv("SEARCH_ADMIN_KEY", "").strip()
    return AzureKeyCredential(key) if key else DefaultAzureCredential()


def openai_client():
    """OpenAI client for the Foundry resource's Azure OpenAI endpoint, signed in with Entra ID
    (az login on your laptop, the managed identity in GitHub Actions). Used for embeddings and the judge model."""
    from openai import OpenAI

    endpoint = need("AZURE_OPENAI_ENDPOINT")  # e.g. https://<resource>.openai.azure.com
    token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    return OpenAI(base_url=f"{endpoint}/openai/v1/", api_key=token)


def get_project():
    from azure.ai.projects import AIProjectClient

    return AIProjectClient(endpoint=need("FOUNDRY_PROJECT_ENDPOINT"), credential=DefaultAzureCredential(), allow_preview=True)


def ask(project, agent_name: str, question: str, version: str | None = None, conversation_id: str | None = None):
    reference = {"type": "agent_reference", "name": agent_name}
    if version:
        reference["version"] = str(version)
    kwargs = {"input": question, "extra_body": {"agent_reference": reference}}
    if conversation_id:
        kwargs["conversation"] = conversation_id
    # tool_choice "required" makes the model call the search tool before answering, so it can't
    # answer from its own (made-up) knowledge. Set "tool_choice": "auto" in rag.config.json to compare.
    tool_choice = load_config().get("tool_choice")
    client = project.get_openai_client()
    if tool_choice and tool_choice != "auto":
        try:
            return client.responses.create(tool_choice=tool_choice, **kwargs)
        except Exception as error:
            if "tool_choice" not in str(error):
                raise
            print(f"Note: the service did not accept tool_choice='{tool_choice}'; asking without it.")
    return client.responses.create(**kwargs)


def tools_used(response) -> list[str]:
    used = []
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", "") or ""
        if item_type.endswith("_call"):
            name = item_type[: -len("_call")]
            if name not in used:
                used.append(name)
    return used


def cited_urls(response) -> list[str]:
    """URLs the model attached as citations, if any."""
    urls = []
    for item in getattr(response, "output", []) or []:
        for part in getattr(item, "content", None) or []:
            for ann in getattr(part, "annotations", None) or []:
                url = getattr(ann, "url", None)
                if url and url not in urls:
                    urls.append(url)
    return urls


def token_usage(response):
    usage = getattr(response, "usage", None)
    return getattr(usage, "total_tokens", None) if usage else None


embeddings_client = openai_client  # older name


def set_output(name: str, value) -> None:
    """Pass a value to later pipeline steps when running in GitHub Actions."""
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def write_summary(markdown: str) -> None:
    """Show a markdown report on the GitHub Actions run page."""
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")
