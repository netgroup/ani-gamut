"""
ANI-Gamut Phase-0: SRv6 A3-T core, datapizza-free.

Re-implements the `create_connection` workflow (which today lives in the datapizza
executor agent's PROMPT, see executor_agent.py steps 1-7) as a deterministic function
`provision_service()`, calling ONLY the datapizza-free modules (state, transactionDB,
messagging) + jsonschema.

There is NO `from datapizza...` import here. This is what the future A3-T MCP tool
`provision_service(intent)` calls; the agent on top becomes the shared NetAiBench agent
(ANI-Gamut decision #1 = Option A-i). See tests/README.md.
"""
import json
from jsonschema import validate, ValidationError

# --- typed intent schemas (lifted verbatim from validation.py, minus the @tool) ---
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
                "ip": {"type": "string"}, "sid": {"type": "string"},
                "interface": {"type": "string"}, "vrf": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
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
            "properties": {"sid": {"type": "string"}, "vrf": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


def validate_msg(msg):
    try:
        if msg.get("type") == "encap":
            validate(instance=msg, schema=ENCAP_SCHEMA)
        elif msg.get("type") == "decap":
            validate(instance=msg, schema=DECAP_SCHEMA)
        else:
            return {"valid": False, "error": "invalid type"}
        return {"valid": True}
    except ValidationError as e:
        return {"valid": False, "error": str(e)}


# --- pure topology helpers (lifted from tools.py, minus @tool / json.dumps wrapping) ---
def _node_id(name):
    return int("".join(c for c in name if c.isdigit()))

def _dt4_sid(router_id, host_id):
    # End.DT4 uSID (F3216, LIB Set 0xf4): 5f00:0:<router>:f4<host>::  (see srv6-addressing-plan-F3216.md)
    return f"5f00:0:{router_id:x}:f4{host_id:02x}::"

def _host_ipv4(state, host):
    return list(state.node_map[host]["ipv4"].values())[0]

def _vrf(state, host):
    return state.node_map[host]["ipv4"]["vrf"]

def _intf(state, node, neighbor):
    for intf, peer in state.node_map[node]["interfaces"].items():
        if peer == neighbor:
            return intf
    return None


def provision_service(state, sender, db, src_host, dst_host):
    """One-directional SRv6 service provisioning as a typed, validated transaction.

    Args:
        state:  state.NetworkTopology instance.
        sender: messagging.MessageSender (real RabbitBroker against the live lab, or a
                fake broker in tests); must expose send(router, msg) and wait_ack(ids).
        db:     transactionDB.dbTransaction instance.
        src_host, dst_host: host node names (e.g. "hs1", "hs5").

    Returns {"status": "success"|"rollback"|"error", "transaction_id": int, ...}.
    Bidirectional service = two calls (forward + reverse), as the planner does today.
    """
    path = state.shortest_path(src_host, dst_host)
    if not path or path[0] != src_host or path[-1] != dst_host or len(path) < 4:
        return {"status": "error", "error": "invalid or too-short path", "path": path}
    first_router, last_router = path[1], path[-2]

    sidh = _dt4_sid(_node_id(last_router), _node_id(dst_host))   # egress PE End.DT4 uSID
    ipv4_dst = _host_ipv4(state, dst_host)
    vrf_src, vrf_dst = _vrf(state, src_host), _vrf(state, dst_host)
    out_intf = _intf(state, first_router, path[2])

    id_encap, id_decap = db.get_messageID(), db.get_messageID()
    encap_msg = {"msg_id": id_encap, "type": "encap",
                 "encap": {"ip": ipv4_dst, "sid": sidh, "interface": out_intf, "vrf": vrf_src}}
    decap_msg = {"msg_id": id_decap, "type": "decap",
                 "decap": {"sid": sidh, "vrf": vrf_dst}}

    for m in (encap_msg, decap_msg):                       # mandatory schema validation
        v = validate_msg(m)
        if not v["valid"]:
            return {"status": "error", "error": "schema validation failed",
                    "details": v.get("error"), "msg": m}

    tid = db.newTransaction(src_host, dst_host, path,
                            {"ip": ipv4_dst, "vrf": vrf_src, "interface": out_intf},
                            {"sid": sidh, "vrf": vrf_dst})

    sender.send(first_router, encap_msg)
    sender.send(last_router, decap_msg)

    if sender.wait_ack([id_encap, id_decap]):
        return {"status": "success", "transaction_id": tid}
    # provisioning failed -> automatic compensating rollback (A3-T property)
    return {"status": "rollback", "transaction_id": tid,
            "rollback": rollback(db, sender, tid)}


def rollback(db, sender, transaction_id):                  # lifted from tools.rollback_transaction
    element = db.get_transaction(transaction_id)
    if element.get("error", "") != "":
        return {"status": "error", "error": element["error"]}
    id1, id2 = db.get_messageID(), db.get_messageID()
    enc_rb = {"msg_id": id1, "type": "encap_rollback",
              "ip": element["encap"]["ip"], "vrf": element["encap"]["vrf"],
              "dev": element["encap"]["interface"]}
    dec_rb = {"msg_id": id2, "type": "decap_rollback",
              "sid": element["decap"]["sid"], "vrf": element["decap"]["vrf"]}
    sender.send(element["path"][1], enc_rb)
    sender.send(element["path"][-2], dec_rb)
    return {"status": "success"} if sender.wait_ack([id1, id2]) else {"status": "error"}
