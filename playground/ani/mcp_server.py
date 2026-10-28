import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from drivers import get_driver
from mcp.server.fastmcp import FastMCP

# Questo file espone i tool via FastMCP

_lab_name: str = ""
_task_file: Path = Path()
_log_file: Path = Path()
_project_root: Path = Path()
_node_kinds: dict[str, str] = {}
_rollback_stacks: dict[str, list[dict[str, Any]]] = {}
_provision_recipe: str = ""   # A3-T: path to the gen_tenants --emit-provision recipe
_level: str = "a1"

# Sono globali perché il server MCP viene avviato una volta per run e
# poi i tool devono sapere su quale lab/task/livello operano.
#
# ANI abstraction level selected at runtime with --level:
#   a0     -> raw interface: only run_shell (docker exec, NO allowlist)
#   a1     -> structured ANI: get_running_config/update_config/execute_validation/
#             rollback, with Tier-1 allowlist (generic guardrail) + auto snapshot
#   a1plus -> like a1 but with the Tier-2 anti-damage blocklist active (ablation)

# Crea il server MCP
mcp = FastMCP("netconfbench-ani")


# Costruisce il nome del container dato il nome del nodo in containerlab.
# Host-aggregator mode (env ANI_HOSTS_AGG): every host hs<N> is hosted by the single
# aggregator container, so it resolves there (the per-host netns is selected by the
# driver at exec time). Empty env (default) = one container per node.
def _clab(node: str) -> str:
    agg = os.environ.get("ANI_HOSTS_AGG", "")
    if agg and re.fullmatch(r"hs(\d+)", node):
        return f"clab-{_lab_name}-{agg}"
    return f"clab-{_lab_name}-{node}"


# Carica il task JSON
def _load_task() -> dict:
    with open(_task_file) as f:
        return json.load(f)


# Dal task ricava lab_file, lo risolve rispetto alla root progetto e controlla che esista
def _resolve_lab_file() -> Path:
    task = _load_task()
    lab_file = task.get("lab_file")
    if not lab_file:
        raise ValueError("Task JSON must contain 'lab_file'")

    lab_path = (_project_root / lab_file).resolve()
    if not lab_path.exists():
        raise FileNotFoundError(f"Lab file not found: {lab_path}")

    return lab_path


# Legge il YAML Containerlab
def _load_lab_yaml() -> dict:
    lab_path = _resolve_lab_file()
    with open(lab_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid lab YAML structure in {lab_path}")

    return data


# Estrae dal YAML lista nodi e lista link in formato leggibile
def _load_topology_from_lab() -> dict:
    lab = _load_lab_yaml()

    topo = lab.get("topology", {})
    nodes_section = topo.get("nodes", {})
    links_section = topo.get("links", [])

    nodes = list(nodes_section.keys())

    links = []
    for link in links_section:
        endpoints = link.get("endpoints", [])
        if len(endpoints) == 2:
            links.append(f"{endpoints[0]} <-> {endpoints[1]}")

    return {
        "nodes": nodes,
        "links": links,
    }


# Costruisce un dict node_name -> kind per selezionare il driver corretto
def _load_node_kinds_from_lab() -> dict[str, str]:
    lab = _load_lab_yaml()
    topo = lab.get("topology", {})
    nodes_section = topo.get("nodes", {})

    result = {}
    for node_name, node_data in nodes_section.items():
        result[node_name] = node_data.get("kind", "linux")

    return result


# Restituisce il driver corretto per il device richiesto
def _driver_for(device: str):
    kind = _node_kinds.get(device, "linux")
    return get_driver(
        kind=kind,
        lab_name=_lab_name,
        log_file=_log_file,
        block_tier2=(_level == "a1plus"),
    )


# Restituisce il kind Containerlab associato a un device
def _kind_for(device: str) -> str:
    return _node_kinds.get(device, "linux")


# Indica se il rollback reale è supportato per il kind del device
def _rollback_supported_for_kind(kind: str) -> bool:
    return kind == "linux"


# Costruisce un blocco informativo uniforme sul supporto rollback di un device
def _rollback_support_info(device: str) -> dict[str, Any]:
    kind = _kind_for(device)
    return {
        "device": device,
        "driver_kind": kind,
        "rollback_supported": _rollback_supported_for_kind(kind),
    }


# Usa docker ps per elencare container attivi
def _list_running_containers() -> list[str]:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.splitlines()


# Controlla se i container attesi dal lab sono attivi e stampa warning se mancano
def _warn_if_lab_not_running() -> None:
    try:
        topology = _load_topology_from_lab()
        nodes = topology.get("nodes", [])
        running = set(_list_running_containers())
        expected = {_clab(node) for node in nodes}
        missing = sorted(expected - running)

        if missing:
            print(
                "WARNING: some lab containers are not running: " + ", ".join(missing),
                file=sys.stderr,
            )
    except Exception as e:
        print(f"WARNING: could not verify lab status: {e}", file=sys.stderr)


# Inizializza gli stack di rollback per tutti i nodi del lab
def _init_rollback_stacks() -> None:
    global _rollback_stacks
    topology = _load_topology_from_lab()
    _rollback_stacks = {node: [] for node in topology.get("nodes", [])}


# Cattura e salva uno snapshot per un device nello stack di rollback
def _push_snapshot(device: str) -> dict[str, Any]:
    driver = _driver_for(device)
    support_info = _rollback_support_info(device)
    snapshot = driver.capture_rollback_state(device)

    snapshot["driver_kind"] = support_info["driver_kind"]
    snapshot["rollback_supported"] = support_info["rollback_supported"]

    _rollback_stacks.setdefault(device, []).append(snapshot)
    return snapshot


def _filesystem_snapshot_info(snapshot: dict[str, Any]) -> dict[str, Any]:
    fs_state = snapshot.get("filesystem", {})
    if not fs_state:
        return {
            "captured": False,
        }

    return {
        "captured": bool(fs_state.get("available")),
        "strategy": fs_state.get("strategy", ""),
        "tracked_paths": fs_state.get("tracked_paths", []),
        "archived_paths": fs_state.get("archived_paths", []),
        "archive_size": fs_state.get("archive_size", 0),
        "manifest_entries": len(fs_state.get("manifest", [])),
        "error": fs_state.get("error", ""),
    }


# Ripristina l'ultimo snapshot disponibile per un device
def _pop_and_restore_snapshot(device: str) -> dict[str, Any]:
    support_info = _rollback_support_info(device)
    stack = _rollback_stacks.get(device, [])

    if not stack:
        return {
            "status": "error",
            "device": device,
            "message": "no rollback snapshot available",
            "remaining_snapshots": 0,
            **support_info,
        }

    snapshot = stack.pop()
    driver = _driver_for(device)
    restore_result = driver.restore_rollback_state(device, snapshot)

    return {
        "status": restore_result.get("status", "unknown"),
        "device": device,
        "restore_result": restore_result,
        "remaining_snapshots": len(stack),
        **support_info,
    }


# ---------------------------------------------------------------------------
# Tool definitions (plain functions). They are registered with the MCP server
# per level by _register_tools_for_level(); see main().
# ---------------------------------------------------------------------------


# Ritorna la topologia intera o filtrata per devices
def get_topology(devices: list[str] | None = None) -> dict:
    """
    Restituisce la topologia del lab (nodi e link) dal YAML del lab.
    Se devices è None o vuoto, restituisce la topologia completa.
    """
    topology = _load_topology_from_lab()

    if devices:
        filtered = {
            "nodes": [n for n in topology["nodes"] if n in devices],
            "links": [l for l in topology["links"] if any(d in l for d in devices)],
        }
        return {"topology": filtered}

    return {"topology": topology}


# [A0] Run a raw command on the device via docker exec, no allowlist
def run_shell(device: str, command: str) -> dict:
    """
    [A0] Run an arbitrary command on the device via docker exec, with NO allowlist
    and no snapshot/rollback. Raw interface, available only at level A0.
    """
    driver = _driver_for(device)
    return driver.run_shell(device, command)


# Restituisce la running config corrente del device tramite il driver corretto
def get_running_config(device: str) -> dict:
    """
    Restituisce la configurazione attiva di un device.
    """
    driver = _driver_for(device)
    return driver.get_running_config(device)


# Applica una lista di comandi dopo aver salvato automaticamente uno snapshot rollback del device
def update_config(device: str, commands: list[str]) -> dict:
    """
    Applica una lista di comandi a un device.
    Prima della modifica viene catturato automaticamente uno snapshot di rollback.

    Per scrivere file di configurazione allowlistati, usare il formato esatto:
    printf %s <base64-utf8> | base64 -d | tee <path> >/dev/null
    Path scrivibili: /etc/frr/frr.conf, /etc/frr/daemons, /etc/frr/vtysh.conf,
    /etc/haproxy/haproxy.cfg, /usr/local/etc/haproxy/haproxy.cfg, /etc/nftables.conf.
    """
    driver = _driver_for(device)
    support_info = _rollback_support_info(device)

    snapshot_info: dict[str, Any]
    try:
        snapshot = _push_snapshot(device)
        snapshot_info = {
            "captured": True,
            "device": device,
            "stack_depth": len(_rollback_stacks.get(device, [])),
            "snapshot_kind": snapshot.get("kind", support_info["driver_kind"]),
            "filesystem": _filesystem_snapshot_info(snapshot),
            **support_info,
        }
    except Exception as e:
        snapshot_info = {
            "captured": False,
            "device": device,
            "error": str(e),
            "stack_depth": len(_rollback_stacks.get(device, [])),
            **support_info,
        }

    result = driver.update_config(device, commands)
    result["rollback_snapshot"] = snapshot_info
    return result


# Esegue un comando read-only di validazione tramite il driver corretto
def execute_validation(device: str, command: str) -> dict:
    """
    Esegue un comando in sola lettura su un device e restituisce il suo output.
    """
    driver = _driver_for(device)
    return driver.execute_validation(device, command)


# Ripristina l'ultimo snapshot disponibile per il device richiesto
def rollback(device: str) -> dict:
    """
    Ripristina il device all'ultimo snapshot salvato.
    """
    return _pop_and_restore_snapshot(device)


# Restituisce informazioni sul numero di snapshot disponibili e sul supporto rollback
def get_rollback_status(device: str | None = None) -> dict:
    """
    Restituisce informazioni sullo stack di rollback per un device o per l'intero lab.
    """
    if device:
        support_info = _rollback_support_info(device)
        return {
            **support_info,
            "available_snapshots": len(_rollback_stacks.get(device, [])),
        }

    return {
        "devices": {
            dev: {
                **_rollback_support_info(dev),
                "available_snapshots": len(stack),
            }
            for dev, stack in _rollback_stacks.items()
        }
    }


# [A3-T] Realize the held-out tenant's service from a typed intent, transactionally.
def provision_service(intent: dict) -> dict:
    """
    [A3-T] Realize the target tenant's service from a typed intent. The agent declares
    WHAT (op + tenant + sites); the layer does the HOW transactionally: snapshot the
    devices -> apply the tenant's recipe (gen_tenants --emit-provision) -> commit, or
    auto-rollback every applied device on the first failure. The agent never sees the
    per-device commands; that is the abstraction.
    """
    from provision import validate_intent, load_recipe, run_transaction
    if not _provision_recipe:
        return {"status": "error",
                "error": "server started without --provision-recipe; provision_service unavailable"}
    err = validate_intent(intent)
    if err:
        return {"status": "error", "error": f"invalid intent: {err}"}
    try:
        recipe = load_recipe(_provision_recipe)
    except Exception as e:
        return {"status": "error", "error": f"cannot load provision recipe: {e}"}

    def _apply(device: str, cmds: list[str]):
        # The A3-T layer is trusted: it applies its own known-good recipe (the gen_tenants
        # realization), so it must NOT pass the A1 agent allowlist, which rejects the
        # oracle's seg6/vrf/flush commands. apply_raw runs them via docker exec with no
        # allowlist, but checks exit codes so a genuine failure rolls the transaction back.
        res = _driver_for(device).apply_raw(device, cmds)
        ok = all(r.get("status") == "success" for r in res.get("results", []))
        return ok, res

    return run_transaction(recipe, _push_snapshot, _apply, _pop_and_restore_snapshot)


# Registra sul server MCP il toolset corrispondente al livello ANI selezionato
def _register_tools_for_level(level: str) -> None:
    # Topology read is infrastructural: available at every level.
    mcp.tool()(get_topology)

    if level == "a0":
        # A0: raw interface, no allowlist, no managed rollback.
        mcp.tool()(run_shell)
    elif level == "a3t":
        # A3-T: one typed-intent tool; the layer realizes the service transactionally.
        mcp.tool()(provision_service)
    else:
        # A1 / A1+: structured ANI with allowlist + snapshot/rollback.
        mcp.tool()(get_running_config)
        mcp.tool()(update_config)
        mcp.tool()(execute_validation)
        mcp.tool()(rollback)
        mcp.tool()(get_rollback_status)


# Condense the MCP server's log flood ("Processing request of type X") into a single
# line with a per-type counter that advances in place (\r), instead of N lines.
import logging as _logging
from collections import Counter as _Counter


class _ReqProgressFilter(_logging.Filter):
    _counts: _Counter = _Counter()

    def filter(self, record: "_logging.LogRecord") -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        prefix = "Processing request of type "
        if not msg.startswith(prefix):
            return True
        typ = msg[len(prefix):].split()[0] if msg[len(prefix):].split() else "?"
        self._counts[typ] += 1
        summary = "  ".join(f"{k}={v}" for k, v in sorted(self._counts.items()))
        sys.stderr.write(f"\r  MCP requests | {summary}    ")
        sys.stderr.flush()
        return False   # suppress the original per-request line


def _install_request_progress() -> None:
    flt = _ReqProgressFilter()
    root = _logging.getLogger()
    if not root.handlers:
        root.addHandler(_logging.StreamHandler())
    loggers = [root] + [lg for lg in _logging.root.manager.loggerDict.values()
                        if isinstance(lg, _logging.Logger)]
    for lg in loggers:
        lg.addFilter(flt)
        for h in list(lg.handlers):
            h.addFilter(flt)


# Avvia il server MCP inizializzando task, lab, driver map, livello e rollback stacks
def main() -> None:
    global _lab_name, _task_file, _log_file, _project_root, _node_kinds, _level, _provision_recipe

    parser = argparse.ArgumentParser(description="NetConfBench MCP Server (ANI)")
    parser.add_argument("--lab", required=True, help="Containerlab lab name")
    parser.add_argument("--task", required=True, help="Path to task JSON file")
    parser.add_argument("--log", default="../logs/agent_commands.jsonl", help="Path for command log output")
    parser.add_argument(
        "--level",
        default="a1",
        choices=["a0", "a1", "a1plus", "a3t"],
        help="ANI abstraction level: a0 (raw run_shell, no allowlist), "
             "a1 (structured, Tier-1 allowlist), a1plus (a1 + Tier-2 anti-damage blocklist), "
             "a3t (typed-intent provision_service, transactional + auto-rollback)",
    )
    parser.add_argument("--provision-recipe", dest="provision_recipe", default="",
                        help="A3-T only: path to the gen_tenants --emit-provision recipe "
                             "(the layer's known-good realization that the agent's intent triggers)")
    args = parser.parse_args()

    _lab_name = args.lab
    _task_file = Path(args.task).resolve()
    _log_file = Path(args.log).resolve()
    _project_root = _task_file.parent.parent.resolve()
    _level = args.level
    _provision_recipe = args.provision_recipe

    _log_file.parent.mkdir(parents=True, exist_ok=True)

    if not _task_file.exists():
        print(f"ERROR: task file not found: {_task_file}", file=sys.stderr)
        sys.exit(1)

    try:
        _resolve_lab_file()
    except Exception as e:
        print(f"ERROR: could not resolve lab file from task: {e}", file=sys.stderr)
        sys.exit(1)

    _node_kinds = _load_node_kinds_from_lab()
    _init_rollback_stacks()
    _register_tools_for_level(_level)

    print(f"ANI server ready | lab={_lab_name} | level={_level} | task={_task_file}", file=sys.stderr)
    _warn_if_lab_not_running()
    _install_request_progress()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
