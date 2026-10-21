"""Expense Claims API – a small Azure Function the agent calls as a tool.

POST /api/claims             submit a claim (only after the employee has confirmed)
GET  /api/claims/{claim_id}  check the status of a claim

It stands in for a real expense system: it validates the claim, applies the
manager-approval rule, stores it in Azure Table Storage and returns a claim ID.
"""
import json
import logging
import os
import random
import string
from datetime import datetime, timezone

import azure.functions as func

# Practice setting: anonymous access so the agent can call it without extra setup.
# In production, protect it with Entra ID and let the agent call it with a managed identity.
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

ALLOWED_CATEGORIES = {"airfare", "lodging", "meal", "client meal", "mileage", "ground transport", "other"}
MAX_ITEM_AMOUNT = 10_000
MANAGER_APPROVAL_THRESHOLD = 1_000  # policy section 9: claims above $1,000 need manager approval
TABLE_NAME = "claims"


# ---------- storage (optional: the API still works if storage isn't configured) ----------

def _table_client():
    """Return a client for the 'claims' table, or None if storage isn't available."""
    try:
        from azure.data.tables import TableServiceClient

        conn = os.getenv("AzureWebJobsStorage", "")
        if conn and ("AccountName=" in conn or conn.startswith("UseDevelopmentStorage")):
            service = TableServiceClient.from_connection_string(conn)
        elif os.getenv("AzureWebJobsStorage__accountName"):
            from azure.identity import DefaultAzureCredential

            account = os.environ["AzureWebJobsStorage__accountName"]
            service = TableServiceClient(f"https://{account}.table.core.windows.net", credential=DefaultAzureCredential())
        else:
            return None
        return service.create_table_if_not_exists(TABLE_NAME)
    except Exception as error:  # never fail the request just because storage is unavailable
        logging.warning("Table storage unavailable: %s", error)
        return None


def _json(body: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status, mimetype="application/json")


def _new_claim_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"CLM-{today}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"


# ---------- validation ----------

def validate_claim(data: dict) -> list[str]:
    """Server-side checks. The agent is not trusted blindly: everything is re-validated here."""
    errors = []
    if data.get("employee_confirmed") is not True:
        errors.append("employee_confirmed must be true. Show the employee a summary and get explicit confirmation before submitting.")
    if not str(data.get("employee_name", "")).strip():
        errors.append("employee_name is required.")
    if not str(data.get("trip_city", "")).strip():
        errors.append("trip_city is required.")
    items = data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        errors.append("items must be a list with 1 to 50 expense items.")
        return errors
    for i, item in enumerate(items, start=1):
        category = str(item.get("category", "")).strip().lower()
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"item {i}: category must be one of {sorted(ALLOWED_CATEGORIES)}.")
        amount = item.get("amount")
        if not isinstance(amount, (int, float)) or not 0 < amount <= MAX_ITEM_AMOUNT:
            errors.append(f"item {i}: amount must be a number between 0 and {MAX_ITEM_AMOUNT}.")
        if not str(item.get("description", "")).strip():
            errors.append(f"item {i}: description is required.")
    return errors


# ---------- endpoints ----------

@app.route(route="claims", methods=["POST"])
def submit_claim(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
    except ValueError:
        return _json({"error": "Request body must be JSON."}, 400)

    errors = validate_claim(data)
    if errors:
        logging.info("Claim rejected: %s", errors)
        return _json({"status": "Rejected", "errors": errors}, 400)

    total = round(sum(float(item["amount"]) for item in data["items"]), 2)
    status = "Pending manager approval" if total > MANAGER_APPROVAL_THRESHOLD else "Submitted"
    claim_id = _new_claim_id()
    submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    claim = {
        "claim_id": claim_id,
        "status": status,
        "employee_name": data["employee_name"].strip(),
        "trip_city": data["trip_city"].strip(),
        "total_amount": total,
        "item_count": len(data["items"]),
        "submitted_at": submitted_at,
    }

    table = _table_client()
    stored = False
    if table is not None:
        try:
            table.create_entity({
                "PartitionKey": "claims",
                "RowKey": claim_id,
                **claim,
                "items_json": json.dumps(data["items"]),
            })
            stored = True
        except Exception as error:
            logging.warning("Could not store claim %s: %s", claim_id, error)

    # Audit log: every submission is recorded (visible in Application Insights)
    logging.info("Claim submitted: %s employee=%s total=%.2f status=%s stored=%s",
                 claim_id, claim["employee_name"], total, status, stored)

    message = (f"Claim {claim_id} for ${total:,.2f} was submitted."
               if status == "Submitted" else
               f"Claim {claim_id} for ${total:,.2f} is over ${MANAGER_APPROVAL_THRESHOLD:,} and was sent to the manager for approval.")
    return _json({**claim, "stored": stored, "message": message}, 201)


@app.route(route="claims/{claim_id}", methods=["GET"])
def get_claim_status(req: func.HttpRequest) -> func.HttpResponse:
    claim_id = req.route_params.get("claim_id", "")
    table = _table_client()
    if table is None:
        return _json({"error": "Claim storage is not configured, so status lookups are unavailable."}, 503)
    try:
        entity = table.get_entity(partition_key="claims", row_key=claim_id)
    except Exception:
        return _json({"error": f"Claim {claim_id} was not found."}, 404)
    return _json({k: entity[k] for k in ("claim_id", "status", "employee_name", "trip_city",
                                          "total_amount", "item_count", "submitted_at") if k in entity})
