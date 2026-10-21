"""Chat with the agent from the terminal, the same way an application would call it.

Usage:
    python scripts/chat.py
Type 'exit' to quit.
"""
from foundry_common import ask, get_project, load_config, token_usage, tools_used


def main() -> None:
    config = load_config()
    project = get_project()
    conversation = project.get_openai_client().conversations.create()  # keeps chat history on the server
    print(f"Chatting with {config['agent_name']}. Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        response = ask(project, config["agent_name"], question, conversation_id=conversation.id)
        print(f"\nAgent: {response.output_text}")
        print(f"       [tools: {', '.join(tools_used(response)) or 'none'} | tokens: {token_usage(response)}]\n")


if __name__ == "__main__":
    main()
