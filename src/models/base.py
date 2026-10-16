
"""Decision model interface. The engine only talks to models through this class.

Every supported provider speaks the same "System One" decision format:

  request   {"model": ..., "state": ..., "questions": {id: question}}
  question  {"type": "choice", "instructions": str, "criteria": {option: meaning}}
            {"type": "noul",   "instructions": str}
            {"type": "score",  "instructions": str, "criteria": [level0, level1, ...]}
  response  {"answers": {id: answer}, ...}
  answer    choice -> {"choice": option, "probabilities": {...}, "confidence": float}
            noul   -> {"noul": p_yes}
            score  -> {"score": float, "probabilities": {...}, "confidence": float}

An adapter only implements _send(state, questions) -> {id: answer}:
  - providers with an official decision SDK use it (SystemOneModel -> typesafe_sdk),
  - the rest extend HttpDecisionModel, which posts this JSON with httpx; such an adapter
    only sets the URL, the auth headers and, if needed, how the response is unwrapped.
The engine uses choice() / noul() / nouls_and_choice(); score() is available for agents
and future features.

Every decision made through choice() / noul() / score() / nouls_and_choice() is recorded
into the current turn's decision list (see `decision_log`), which Agent.turn() returns in
TurnResult.decisions. Nothing is printed.
"""
from contextvars import ContextVar

import httpx

DEFAULT_MIN_CONF = 0.6


class LowConfidence(Exception):
    """A Choice came back below the model's min_conf; the engine falls back."""


class DecisionModelError(Exception):
    """The provider returned an error or an unexpected response."""


class DecisionModelNotFound(DecisionModelError):
    """The API key is missing/rejected, or the requested model is unavailable."""


def _model_unavailable(status, detail=""):
    if status in (401, 403, 404):
        return True
    text = str(detail).lower()
    return status in (400, 422) and any(message in text for message in (
        "model_not_found", "model not found", "unknown model", "invalid model",
        "model does not exist", "invalid api key", "invalid api token",
    ))


# The list that collects this turn's decisions. Agent.turn() sets it for the duration of a
# turn; a ContextVar keeps concurrent turns (threads, async tasks) separate.
decision_log = ContextVar("decisionact_decision_log", default=None)


def _record(**entry):
    decisions = decision_log.get()
    if decisions is not None:
        decisions.append(entry)


class DecisionModel:
    """Base class for every decision model provider.

    Subclasses implement `_send(state, questions)`. `min_conf` is the lowest Choice
    confidence the engine trusts for this model; models are calibrated differently, so
    tune it per model.
    """

    name = "decision-model"

    def __init__(self, model, min_conf=DEFAULT_MIN_CONF):
        if not isinstance(model, str) or not model.strip():
            raise DecisionModelNotFound("A decision model name is required")
        self.model, self.min_conf = model, min_conf

    def __repr__(self):
        return f"{type(self).__name__}(model={self.model!r})"

    # ---------- raw call ----------
    def ask(self, state, questions):
        """Send any number of questions about one state in a single request.
        `questions` = {id: question in the System One format}. Returns {id: answer dict}."""
        answers = self._send(state, questions)
        missing = set(questions) - set(answers)
        if missing:
            raise DecisionModelError(f"{self}: no answer for {sorted(missing)}")
        return answers

    def _send(self, state, questions):
        raise NotImplementedError

    # ---------- helpers used by the engine ----------
    def choice(self, state, question, options, label, min_conf=None):
        """Pick one key of `options` ({key: description}). Raises LowConfidence."""
        min_conf = self.min_conf if min_conf is None else min_conf
        a = self.ask(state, {"q": {"type": "choice", "instructions": question,
                                   "criteria": options}})["q"]
        pick, conf = a["choice"], a.get("confidence", 0.0)
        _record(step=label, type="choice", answer=pick, confidence=conf,
                low_confidence=conf < min_conf)
        if conf < min_conf:
            raise LowConfidence(question)
        return pick

    def noul(self, state, question, label):
        """Yes/no question. Returns the probability of yes (0..1)."""
        p = self.ask(state, {"q": {"type": "noul", "instructions": question}})["q"]["noul"]
        _record(step=label, type="noul", answer=p)  # answer = probability of yes
        return p

    def score(self, state, question, levels, label):
        """Ordered rubric (levels from 0). Returns (expected score, confidence)."""
        a = self.ask(state, {"q": {"type": "score", "instructions": question,
                                   "criteria": list(levels)}})["q"]
        _record(step=label, type="score", answer=a["score"], confidence=a.get("confidence", 0.0))
        return a["score"], a.get("confidence", 0.0)

    def nouls_and_choice(self, state, noul_questions, choice_question, options, label,
                         choice_label):
        """One request: several Nouls ({key: question}) + one Choice.
        Returns ({key: p_yes}, choice, confidence)."""
        questions = {k: {"type": "noul", "instructions": q} for k, q in noul_questions.items()}
        questions["_choice"] = {"type": "choice", "instructions": choice_question,
                                "criteria": options}
        answers = self.ask(state, questions)
        p = {k: answers[k]["noul"] for k in noul_questions}
        c = answers["_choice"]
        conf = c.get("confidence", 0.0)
        for k, v in p.items():
            _record(step=f"{label} / {k.replace('_', ' ')}", type="noul", answer=v)
        _record(step=f"{label} / {choice_label}", type="choice", answer=c["choice"],
                confidence=conf, low_confidence=conf < self.min_conf)
        return p, c["choice"], conf


class HttpDecisionModel(DecisionModel):
    """A provider without a decision SDK: posts the System One JSON with httpx.
    Subclasses pass `url` and `headers`, and may override `_unwrap`."""

    def __init__(self, model, url, headers, min_conf=DEFAULT_MIN_CONF, timeout=30.0):
        super().__init__(model, min_conf)
        self.url, self.headers = url, headers
        self._client = httpx.Client(timeout=timeout)

    def _send(self, state, questions):
        body = {"model": self.model, "state": state, "questions": questions}
        try:
            response = self._client.post(self.url, json=body,
                                         headers={"Content-Type": "application/json",
                                                  **self.headers})
        except httpx.HTTPError as e:
            raise DecisionModelError(f"{self}: request failed: {e}") from e
        if response.status_code >= 400:
            if _model_unavailable(response.status_code, response.text):
                raise DecisionModelNotFound(
                    f"{self}: API key is invalid or the model was not found "
                    f"(HTTP {response.status_code})")
            raise DecisionModelError(f"{self}: HTTP {response.status_code}: "
                                     f"{response.text[:300]}")
        answers = self._unwrap(response.json()).get("answers")
        if not isinstance(answers, dict):
            raise DecisionModelError(f"{self}: response has no 'answers': {response.text[:300]}")
        return answers

    def _unwrap(self, body):
        """Provider-specific envelope removal; most return the answers at the top level."""
        return body


def bearer(api_key, provider):
    if not isinstance(api_key, str) or not api_key.strip():
        raise DecisionModelNotFound(f"{provider}: API key is required")
    return {"Authorization": f"Bearer {api_key}"}


