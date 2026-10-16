
"""TypeSafe Jev through the official SDK (typesafe_sdk). base_url lets the same SDK reach
any server that speaks TypeSafe's /v1/systemone API (e.g. a self-hosted compatible model).
"""
from .base import DecisionModel, DecisionModelError, DecisionModelNotFound, _model_unavailable


class SystemOneModel(DecisionModel):
    """SystemOneModel(api_key, model="jev-latest", base_url=None)"""

    name = "systemone"

    def __init__(self, api_key=None, model="jev-latest", base_url=None, min_conf=0.6, timeout=30.0):
        if not isinstance(api_key, str) or not api_key.strip():
            raise DecisionModelNotFound("SystemOneModel: API key is required")
        super().__init__(model, min_conf)
        try:
            import typesafe_sdk
        except ImportError as e:  # only needed when this model is used
            raise ImportError("SystemOneModel needs the TypeSafe SDK: pip install typesafe-sdk") from e
        self._sdk = typesafe_sdk
        self._client = typesafe_sdk.TypeSafeClient(api_key=api_key, model=model,
                                                   base_url=base_url, timeout=timeout)

    def _question(self, q):
        """System One question dict -> SDK question object."""
        kinds = {"choice": self._sdk.Choice, "noul": self._sdk.Noul, "score": self._sdk.Score}
        args = {"instructions": q["instructions"]}
        if q.get("criteria") is not None:
            args["criteria"] = q["criteria"]
        return kinds[q["type"]](**args)

    def _send(self, state, questions):
        try:
            response = self._client.system_one(
                state, {qid: self._question(q) for qid, q in questions.items()})
        except self._sdk.TypeSafeError as e:
            status = getattr(e, "status", getattr(e, "status_code", None))
            if _model_unavailable(status, getattr(e, "body", "")):
                raise DecisionModelNotFound(
                    f"{self}: API key is invalid or the model was not found") from e
            raise DecisionModelError(f"{self}: {e}") from e
        return {qid: answer.model_dump() for qid, answer in response.answers.items()}
