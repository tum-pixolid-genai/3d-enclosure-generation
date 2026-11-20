"""Local Ollama extraction into the existing Design Spec v0.1."""

import argparse
from dataclasses import dataclass
import http.client
import json
from pathlib import Path
import re
import sys

from jsonschema import ValidationError

if __package__:
    from .agent import PROJECT_DIR, finite_float, load_validator, reject_json_constant, save_design
    from .capability_check import check_capability
else:
    from agent import PROJECT_DIR, finite_float, load_validator, reject_json_constant, save_design
    from capability_check import check_capability


MODEL = "qwen3:4b-instruct"
PORT = 11439
TIMEOUT = 120
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 768}
PROMPT_PATH = PROJECT_DIR / "prompts/system_prompt_llm_v0.2.md"
REQUEST_SCHEMA = PROJECT_DIR / "schemas/request.schema.json"
DESIGN_SCHEMA = PROJECT_DIR / "schemas/design_spec.schema.json"
PROGRAM_FIELDS = ("task_id", "schema_version", "assumptions")
USAGE_FIELDS = (
    "total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
    "eval_count", "eval_duration", "done_reason",
)


class AgentError(Exception):
    def __init__(self, code, message, *, raw_reply=None, usage=None):
        super().__init__(message)
        self.code = code
        self.raw_reply = raw_reply
        self.usage = usage


@dataclass(frozen=True)
class Extraction:
    design_spec: dict
    raw_reply: str
    usage: dict


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data):
    return json.loads(
        data, object_pairs_hook=unique_object,
        parse_float=finite_float, parse_constant=reject_json_constant,
    )


def ollama_request(path, payload=None, *, port=PORT):
    """Use a direct loopback connection with no proxy or redirect handling."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    try:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        method = "GET" if body is None else "POST"
        connection.request(method, path, body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise AgentError("ollama_http_error", f"Ollama returned HTTP {response.status}.")
        data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise AgentError("ollama_response_error", "Ollama response exceeded the size limit.")
        return parse_json(data)
    except TimeoutError as error:
        raise AgentError("ollama_timeout", f"Ollama exceeded the {TIMEOUT}s socket timeout.") from error
    except (OSError, http.client.HTTPException) as error:
        raise AgentError("ollama_connection_error", f"Ollama connection failed: {error}") from error
    except (ValueError, RecursionError) as error:
        raise AgentError("ollama_response_error", "Ollama returned malformed response JSON.") from error
    finally:
        connection.close()


class LLMAgent:
    def __init__(self, *, port=PORT, chat=None):
        self.request_validator = load_validator(REQUEST_SCHEMA)
        self.design_validator = load_validator(DESIGN_SCHEMA)
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        schema = self.design_validator.schema
        self.generation_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                key: value for key, value in schema["properties"].items() if key not in PROGRAM_FIELDS
            },
            "required": [key for key in schema["required"] if key not in PROGRAM_FIELDS],
        }
        self.port = port
        self.chat = chat

    def extract(self, request):
        try:
            self.request_validator.validate(request)
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", request["task_id"]):
                raise ValidationError("task_id contains unsupported characters")
        except ValidationError as error:
            raise AgentError("invalid_request", error.message) from error
        if request.get("language", "en") != "en":
            raise AgentError("unsupported_language", "This pilot accepts English requests.")

        payload = {
            "model": MODEL,
            "stream": False,
            "format": self.generation_schema,
            "options": OPTIONS,
            "keep_alive": "10m",
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps({
                    "request_text": request["request_text"], "language": "en",
                }, ensure_ascii=False)},
            ],
        }
        response = (
            self.chat(payload) if self.chat is not None
            else ollama_request("/api/chat", payload, port=self.port)
        )
        message = response.get("message") if isinstance(response, dict) else None
        raw_reply = message.get("content") if isinstance(message, dict) else None
        usage = {key: response[key] for key in USAGE_FIELDS if isinstance(response, dict) and key in response}
        if not isinstance(raw_reply, str) or response.get("done") is not True:
            raise AgentError("ollama_response_error", "Missing completed model response.",
                             raw_reply=raw_reply, usage=usage)
        if response.get("done_reason") not in (None, "stop"):
            raise AgentError("incomplete_generation", "Ollama stopped before completing normally.",
                             raw_reply=raw_reply, usage=usage)
        try:
            fields = parse_json(raw_reply)
        except (ValueError, RecursionError) as error:
            raise AgentError("invalid_model_json", str(error), raw_reply=raw_reply, usage=usage) from error
        if not isinstance(fields, dict) or fields.keys() & set(PROGRAM_FIELDS):
            raise AgentError("invalid_design", "Expected an object containing only model-owned fields.",
                             raw_reply=raw_reply, usage=usage)
        design_spec = {
            "schema_version": self.design_validator.schema["properties"]["schema_version"]["const"],
            "task_id": request["task_id"],
            **fields,
            "assumptions": ["Board dimensions and connector positions require verified reference data."],
        }
        try:
            self.design_validator.validate(design_spec)
        except ValidationError as error:
            location = ".".join(map(str, error.absolute_path)) or "root"
            raise AgentError("invalid_design", f"{location}: {error.message}",
                             raw_reply=raw_reply, usage=usage) from error
        return Extraction(design_spec, raw_reply, usage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        request = parse_json(args.request.read_text(encoding="utf-8"))
        extraction = LLMAgent().extract(request)
    except AgentError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RecursionError) as error:
        print(f"setup_or_input_error: {error}", file=sys.stderr)
        return 2
    design = extraction.design_spec
    gate = check_capability(design, request=request)
    target = args.output_dir / f"{design['task_id']}_design_spec.json"
    try:
        save_design(target, json.dumps(design, indent=2, allow_nan=False) + "\n")
    except OSError as error:
        print(f"output_error: {error}", file=sys.stderr)
        return 3
    print(json.dumps({"design_spec_path": str(target), "capability": gate, "usage": extraction.usage},
                     indent=2, ensure_ascii=True))
    return {"allow": 0, "clarification_required": 4, "unsupported": 5, "review_required": 6}[gate["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
