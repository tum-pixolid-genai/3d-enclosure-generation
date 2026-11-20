"""Keep the model draft and semantic corrections separately auditable."""

from dataclasses import dataclass

from .capability_check import check_capability
from .llm_agent import AgentError, Extraction, LLMAgent
from .semantic_checks import ground_draft


@dataclass(frozen=True)
class CheckedExtraction:
    model: Extraction
    design_spec: dict
    capability: dict
    changes: list
    issues: list


class HardenedAgent:
    def __init__(self, model: LLMAgent):
        self.model = model

    def extract(self, request):
        text = request.get("request_text") if isinstance(request, dict) else None
        if isinstance(text, str) and len(text) > 4096:
            raise AgentError("invalid_request", "The experimental request limit is 4096 characters.")
        raw = self.model.extract(request)
        design, normalized_request, changes, issues = ground_draft(request, raw.design_spec)
        self.model.design_validator.validate(design)
        gate = check_capability(design, request=normalized_request)
        return CheckedExtraction(raw, design, gate, changes, issues)
