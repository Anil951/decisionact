
"""Cloudflare Clef / Clef-flash on Workers AI. Needs an account id and an API token.
Uses the Workers AI decision endpoint."""
from .base import DecisionModelError, HttpDecisionModel, bearer


class CloudflareModel(HttpDecisionModel):
    """CloudflareModel(api_token, account_id, model="clef")   model: "clef" or "clef-flash" """

    name = "cloudflare"

    def __init__(self, api_token=None, account_id=None, model="clef", **kw):
        headers = bearer(api_token, "CloudflareModel")
        if not account_id:
            raise ValueError("CloudflareModel: account_id is required")
        url = (f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
               f"/ai/run/@cf/cloudflare/{model}")
        super().__init__(model, url, headers, **kw)

    def _unwrap(self, body):
        """Workers AI wraps results: {"result": {...}, "success": true, "errors": [...]}."""
        if isinstance(body, dict) and "result" in body:
            if body.get("success") is False:
                raise DecisionModelError(f"{self}: {body.get('errors')}")
            return body["result"]
        return body


