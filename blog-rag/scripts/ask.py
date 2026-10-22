"""Ask the blog reader agent questions from the terminal.

    python scripts/ask.py                          # interactive chat
    python scripts/ask.py "What changed in pipelines over the last three releases?"
"""
import sys

from common import ask, cited_urls, get_project, load_config, token_usage, tools_used


def show(response) -> None:
    print(f"\nAgent: {response.output_text}")
    urls = cited_urls(response)
    if urls:
        print("       citations: " + ", ".join(urls))
    print(f"       [tools: {', '.join(tools_used(response)) or 'none'} | tokens: {token_usage(response)}]\n")


def main() -> None:
    cfg = load_config()
    project = get_project()
    if len(sys.argv) > 1:
        show(ask(project, cfg["agent_name"], " ".join(sys.argv[1:])))
        return
    conversation = project.get_openai_client().conversations.create()
    print(f"Chatting with {cfg['agent_name']}. Type 'exit' to quit.\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            show(ask(project, cfg["agent_name"], question, conversation_id=conversation.id))


if __name__ == "__main__":
    main()
