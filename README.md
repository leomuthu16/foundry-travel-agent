# Travel Expense Agent – deployment kit

Deploys the Contoso Travel & Expense Policy Assistant to Microsoft Foundry from Git,
tests it automatically, and promotes it from DEV to PROD with GitHub Actions.

```
agent/agent.config.json      model, tools, vector store ID
agent/instructions.md        the agent's instructions
tests/test_cases.json        test questions and expected answers (the quality gate)
agent/tools/expense_claims.openapi.json   OpenAPI spec for the claims tool (Step 10)
agent/instructions_claims.md extra instructions added when the claims tool is enabled
functions/expense-claims-api Azure Function: the Claims API the agent calls (Step 10)
scripts/deploy_agent.py      creates a new agent version from the files above
scripts/run_tests.py         runs the test questions; fails if any answer is wrong
scripts/chat.py              chat with the agent from the terminal
.github/workflows/deploy-agent.yml   the CI/CD pipeline
```

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
az login
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"

python scripts/chat.py          # 1. call the agent from code
python scripts/run_tests.py     # 2. run the automated tests
python scripts/deploy_agent.py  # 3. deploy a new version from Git
```

Set `file_search.vector_store_id` in `agent/agent.config.json` first (the `vs_...` ID
shown under File search in the portal).

To switch on the claims tool, set `claims_api.enabled` and `claims_api.base_url` in
`agent/agent.config.json`, or set the `CLAIMS_API_URL` environment variable.

See the build guide: Step 9 (deployment and GitHub Actions) and Step 10 (claims tool).
