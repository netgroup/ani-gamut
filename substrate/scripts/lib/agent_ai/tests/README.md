# SRv6 A3-T core — datapizza-free extraction (ANI-Gamut Phase 0)

**Status:** extractability spike, validated — 12/12 smoke checks green (2026-06-22).

## Why this exists
ANI-Gamut treats the agent–network *interface abstraction level* as the experimental
variable and compares A0/A1/A3-T under a single shared agent. Decision #1 (Option A-i):
the A3-T level (typed declarative SRv6 service intent) is driven by the **same** agent
used for A0/A1 — the NetAiBench agent + `model_registry` — **not** by this repo's
datapizza planner/executor. `srv6_core.py` is the first step: the SRv6 provisioning core
made callable **without datapizza**, ready to sit behind the future A3-T MCP tool
`provision_service(intent)`.

## Files
- `../srv6_core.py` — the extracted core. Pure, dependency-injected, no `datapizza` import
  (only `json` + `jsonschema`):
  - `provision_service(state, sender, db, src_host, dst_host)` — one-directional SRv6
    service as a typed, schema-validated transaction with automatic compensating
    rollback. Re-implements the `create_connection` workflow that today lives in the
    datapizza executor agent's PROMPT (`executor_agent.py`, steps 1-7).
  - `rollback(db, sender, transaction_id)` — compensating rollback (from
    `tools.rollback_transaction`).
  - `validate_msg(msg)` — encap/decap JSON-schema validation (schemas inlined from
    `validation.py`).
- `fake_broker.py` — RabbitMQ-free broker double implementing the RabbitBroker contract
  (`send`, `wait_messageIDs`) so `messagging.MessageSender(FakeBroker())` runs with no broker.
- `test_srv6_core.py` — the smoke test (no datapizza, no RabbitMQ, no Containerlab).

## How it maps to the existing code
- **Reused unchanged:** `state.py` (topology/SID/VRF), `transactionDB.py` (transaction
  store), `messagging.py::MessageSender` (broker-swappable).
- **Dropped for A3-T:** `executor_agent.py` / `planner_agent.py` (datapizza `Agent` +
  `GoogleClient`). The orchestration they did via prompt is now `provision_service()`.
- **Transition note:** `tools.py` / `validation.py` keep their `@tool` wrappers for now;
  in the build phase they should *delegate* to `srv6_core` so there is a single source of
  truth (no duplicated logic), and `validation.py`'s schemas should be de-`@tool`'d and
  shared with `srv6_core`.

## Run the test (no lab required)
```bash
pip install networkx pyyaml jsonschema pika      # agent_ai deps; NO datapizza needed
python3 scripts/lib/agent_ai/tests/test_srv6_core.py
# expect: "SUMMARY: 12 passed, 0 failed" and exit code 0
```

## What this proves / does not prove
- **Proves:** the A3-T core is datapizza-free and broker-swappable; provisioning + schema
  validation + transaction + automatic rollback run end-to-end against the real topology
  model.
- **Does not prove:** the kernel-level end-to-end on the live Containerlab + RabbitMQ +
  router daemons (those are unchanged here; validate when the lab runs).

## TODO before production use (hardening — from the Phase-0 design)
- `transactionDB`: make thread-safe + persistent (today in-memory, single-threaded).
- `validator_handler.py`: parametrize (remove hardcoded `h1`/`h2` IPs, `sid_list`,
  `expected_sid`, and the module-global `reply_received`).
- schema validation for `rollback`/`validate` messages (today only encap/decap).
- generalize to the north-south egress service class; bidirectional service = two
  `provision_service` calls.
- wire `provision_service` behind the unified ANI as the A3-T MCP tool, driven by the
  shared NetAiBench agent → multi-model support comes for free (datapizza was Google-only).

## Design context (shared OneDrive folder `articoli/26-cnsm-agentic-ai`)
`ani-gamut-phase0-design.md` (Phase-0 design) and
`ani-gamut-spike-srv6-extractability.md` (this spike's write-up).
