from pydantic import BaseModel, ValidationError
from typing import Literal, List
import ipaddress
import networkx as nx

class UpdateRouterAction(BaseModel):
    action: Literal["update_router_metadata"]
    router: str
    field: Literal["sid","ipv6","role"]
    value: str

class SendSRv6PathAction(BaseModel):
    action: Literal["send_srv6_path"]
    router: str
    destination: str
    segments: List[str]

def validate_ipv6(addr: str):
    try:
        ipaddress.IPv6Address(addr)
    except ipaddress.AddressValueError:
        raise ValueError(f"Invalid IPv6 address: {addr}")

def validate_update_router(action, registry):
    UpdateRouterAction(**action)
    if action["router"] not in registry.routers:
        raise ValueError(f"Router {action['router']} not found")
    if action["field"] in ["sid","ipv6"]:
        validate_ipv6(action["value"])

def validate_send_srv6_path(action, registry, graph):
    SendSRv6PathAction(**action)
    if action["router"] not in registry.routers:
        raise ValueError(f"Router {action['router']} not found")
    if action["destination"] not in registry.routers:
        raise ValueError(f"Destination {action['destination']} not found")
    for seg in action["segments"]:
        if seg not in registry.routers:
            raise ValueError(f"Segment router {seg} not found")
    path = nx.shortest_path(graph, source=action["router"], target=action["destination"])
    for seg in action["segments"]:
        if seg not in path:
            raise ValueError(f"Segment {seg} not in shortest path from {action['router']} to {action['destination']}")
