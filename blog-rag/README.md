# Blog RAG prototype

A small replica of a blog platform's search pipeline, extended with an AI reader assistant:
sample posts are chunked, embedded and indexed in Azure AI Search (like the platform's
refresh functions would do), and a Microsoft Foundry agent answers questions with hybrid
search and citations.

```
content/posts/          sample blog posts (fictional product "Contoso DataHub")
content/new_posts/      a later post, used to test freshness
rag.config.json         index, embedding model, agent and search settings
agent_instructions.md   the agent's instructions
scripts/ingest.py       --full or --incremental refresh into Azure AI Search
scripts/create_agent.py creates the agent with the Azure AI Search tool
scripts/ask.py          ask questions from the terminal
scripts/run_tests.py    test questions (--phase auto | baseline | fresh)
scripts/evaluate.py     scores answers for accuracy (judge model) and citations; quality gate
tests/eval_set.json     evaluation questions with reference answers and expected source posts
pipeline/               GitHub Actions workflows: deploy (dev -> prod) and scheduled refresh
```

Copy this folder into your repository as `blog-rag/` and the files in `pipeline/` into
`.github/workflows/` (guide steps R13 and R14). INDEX_NAME and AGENT_NAME override the
config per environment.

Environment variables (PowerShell):

```powershell
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"
$env:AZURE_OPENAI_ENDPOINT    = "https://<resource>.openai.azure.com"
$env:FOUNDRY_RESOURCE_KEY     = "<Foundry resource key, used by the search vectorizer>"
$env:SEARCH_ENDPOINT          = "https://<search-service>.search.windows.net"
$env:SEARCH_ADMIN_KEY         = "<search admin key>"
```

See Blog_RAG_Prototype_Guide.docx for the full steps.
