from datapizza.tools import tool
from jsonschema import validate, ValidationError
import json
ENCAP_SCHEMA = {
    "type": "object",
    "required": ["msg_id", "type", "encap"],
    "properties": {
        "msg_id": {"type": "integer"},
        "type": {"const": "encap"},
        "encap": {
            "type": "object",
            "required": ["ip", "sid", "interface", "vrf"],
            "properties": {
                "ip": {"type": "string"},
                "sid": {"type": "string"},
                "interface": {"type": "string"},
                "vrf": {"type": "string"}
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}


DECAP_SCHEMA = {
    "type": "object",
    "required": ["msg_id", "type", "decap"],
    "properties": {
        "msg_id": {"type": "integer"},
        "type": {"const": "decap"},
        "decap": {
            "type": "object",
            "required": ["sid", "vrf"],
            "properties": {
                "sid": {"type": "string"},
                "vrf": {"type": "string"}
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}

@tool
def validate_srv6_message_schema(msg: dict):
    """
    Strict validation using JSON Schema.

    Returns:
      - {"valid": True, "message": msg}
      - {"valid": False, "error": "...", "details": "..."}
    """

    try:
        if msg.get("type") == "encap":
            validate(instance=msg, schema=ENCAP_SCHEMA)
        elif msg.get("type") == "decap":
            validate(instance=msg, schema=DECAP_SCHEMA)
        else:
            return json.dumps({
                "valid": False,
                "error": "Invalid type (must be encap or decap)"
            },indent=2)

        return json.dumps({
            "valid": True,
            "message": msg
        },indent=2)

    except ValidationError as e:
        return json.dumps({
            "valid": False,
            "error": "Schema validation failed",
            "details": str(e)
        },indent=2)