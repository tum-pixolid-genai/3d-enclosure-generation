
from os import getenv

from jsonschema import ValidationError

from agent.agent import PROJECT_DIR, extract_design, load_validator
from agent.capability_check import check_capability
from agent.hardened_agent import HardenedAgent
from agent.llm_agent import PORT, AgentError, LLMAgent

# Load the Agent's input and output JSON Schemas
request_validator = load_validator(
    PROJECT_DIR / "schemas" / "request.schema.json"
)

design_validator = load_validator(
    PROJECT_DIR / "schemas" / "design_spec.schema.json"
)


agent_mode = getenv("PIXOLID_TEXT_AGENT", "mock")
if agent_mode not in {"mock", "llm"}:
    raise ValueError("PIXOLID_TEXT_AGENT must be mock or llm")

text_agent = (
    HardenedAgent(LLMAgent(port=int(getenv("PIXOLID_OLLAMA_PORT", str(PORT)))))
    if agent_mode == "llm"
    else None
)


def run_agent(agent_request: dict) -> tuple[dict, dict]:
    try:
        request_validator.validate(agent_request)
    except ValidationError as error:
        raise AgentError("invalid_request", error.message) from error

    if text_agent is not None:
        try:
            extraction = text_agent.extract(agent_request)
        except ValidationError as error:
            raise AgentError("invalid_design", error.message) from error
        return extraction.design_spec, extraction.capability

    design_spec = extract_design(agent_request)
    design_validator.validate(design_spec)
    return design_spec, check_capability(design_spec, request=agent_request)
