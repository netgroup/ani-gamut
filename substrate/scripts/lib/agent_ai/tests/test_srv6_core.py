"""Smoke test for srv6_core: drive the SRv6 A3-T core with NO datapizza, NO RabbitMQ,
NO Containerlab. Reuses the real state / transactionDB / messagging.MessageSender modules
with a fake broker. A green run is the data point for ANI-Gamut decision #1 (Option A-i).

Run:  python3 scripts/lib/agent_ai/tests/test_srv6_core.py
Deps: networkx, pyyaml, jsonschema, pika  (NO datapizza, NO running lab)
"""
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_AI = os.path.dirname(HERE)                 # scripts/lib/agent_ai
sys.path.insert(0, AGENT_AI)                     # state / transactionDB / messagging / srv6_core
sys.path.insert(0, HERE)                         # fake_broker


def _find_topo(start):
    d = start
    for _ in range(8):
        cand = os.path.join(d, "topo.yaml")
        if os.path.exists(cand):
            return cand
        d = os.path.dirname(d)
    raise FileNotFoundError("topo.yaml not found above " + start)


from state import NetworkTopology
from transactionDB import dbTransaction
from messagging import MessageSender              # real class, reused with a fake broker
from fake_broker import FakeBroker
import srv6_core

TOPO = _find_topo(HERE)
PASS, FAIL = [], []
def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)

# 0) the core and its deps pulled in NO datapizza module
check("no datapizza imported by the core", "datapizza" not in sys.modules)

state = NetworkTopology(TOPO)
src, dst = "hs1", "hs5"
path = state.shortest_path(src, dst)
print("path", src, "->", dst, ":", path)

# 1) HAPPY PATH (broker acks success)
db = dbTransaction(); broker = FakeBroker(ack_results=[True]); sender = MessageSender(broker)
res = srv6_core.provision_service(state, sender, db, src, dst)
print("happy result:", res)
check("happy: status == success", res.get("status") == "success")
check("happy: exactly 2 messages sent", len(broker.sent) == 2)
topics = [t for t, _ in broker.sent]; msgs = [m for _, m in broker.sent]
check("happy: sent to first then last router",
      topics == [f"router.{path[1]}.commands", f"router.{path[-2]}.commands"])
check("happy: encap message schema-valid", srv6_core.validate_msg(msgs[0])["valid"])
check("happy: decap message schema-valid", srv6_core.validate_msg(msgs[1])["valid"])
check("happy: SIDH consistent encap/decap", msgs[0]["encap"]["sid"] == msgs[1]["decap"]["sid"])
check("happy: transaction recorded",
      db.get_transaction(res["transaction_id"]).get("error", "") == "")

# 2) FAILURE PATH (provisioning ack fails -> automatic compensating rollback, which acks ok)
db2 = dbTransaction(); broker2 = FakeBroker(ack_results=[False, True]); sender2 = MessageSender(broker2)
res2 = srv6_core.provision_service(state, sender2, db2, src, dst)
print("fail result:", res2)
check("fail: status == rollback", res2.get("status") == "rollback")
check("fail: rollback succeeded", res2.get("rollback", {}).get("status") == "success")
check("fail: 2 provisioning + 2 rollback messages", len(broker2.sent) == 4)
check("fail: rollback message types correct",
      {m.get("type") for _, m in broker2.sent[2:]} == {"encap_rollback", "decap_rollback"})

print(f"\nSUMMARY: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
