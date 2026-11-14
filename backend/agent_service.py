
from agent.agent import PROJECT_DIR, extract_design, load_validator

# Load the Agent's input and output JSON Schemas
request_validator = load_validator(
    PROJECT_DIR / "schemas" / "request.schema.json"
)

design_validator = load_validator(
    PROJECT_DIR / "schemas" / "design_spec.schema.json"
)


def run_agent(agent_request: dict) -> dict:
    # Step 1: Validate the request
    request_validator.validate(agent_request)

    # Step 2: Call the Text-to-Design Agent
    design_spec = extract_design(agent_request)

    # Step 3: Validate the Agent's output
    design_validator.validate(design_spec)

    # Step 4: Return the design specification
    return design_spec
