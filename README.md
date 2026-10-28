# ANI-Gamut

Code and project page for **ANI-Gamut** — *Benchmarking Agent Reliability across the
Gamut of Agent–Network Interface Abstractions* (CNSM 2026).

- **Project page:** https://netgroup.github.io/ani-gamut/
- **Extended version:** https://arxiv.org/abs/2609.22723

This is the first reproducible release of the playground, accompanying the CNSM 2026 paper
(git tag `cnsm2026`).

## Repository layout

| Folder | Content | License |
|---|---|---|
| `playground/` | Harness (agent ↔ network interface at levels A0 / A1 / A1+ / A3-T), seeded scenario generator, oracle, fault layer, campaign runner and analysis. Derived from NetAiBench. | Apache-2.0 |
| `substrate/` | SRv6 data-center substrate (Containerlab topology, node image, boot scripts, worker-topology generator). | GPL-3.0 |
| `docs/` | Project page (GitHub Pages). | — |

## Where the paper's components live

| Component (paper) | Code |
|---|---|
| ANI levels A0 / A1 / A1+ / A3-T | `playground/ani/mcp_server.py`, `playground/ani/drivers/linux_driver.py`, `playground/ani/provision.py`, `playground/agent/` |
| Seeded, layered scenario generator | `playground/tools/gen_tenants.py` |
| Composition of a scenario | substrate topology (`substrate/topo.yaml`, worker topologies from `substrate/deploy/gen-worker-topos.py`) + generator parameters (seed, tenants, overlap, operation) passed by `playground/tools/run_pilot.py` |
| Oracle (success and collateral damage) | `playground/tools/gen_tenants.py --mode verify`, `playground/tools/prober.py` |
| Out-of-band fault layer | `playground/tools/fault_layer.py` |
| Campaign and paired analysis | `playground/tools/run_pilot.py`, `playground/tools/analyze.py` |

## Quick start

1. **Testbed VM** (Ubuntu 24.04, 4 vCPU, 16 GB RAM): follow `substrate/deploy/VM-SETUP.md`
   (`provision-vm.sh`, `preflight-srv6.sh`, `make docker`).
2. **Playground environment**, from `playground/`:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   echo "ANTHROPIC_API_KEY=<your key>" > .env
   ```
3. **Run a campaign and analyze it**, from `playground/`:
   ```bash
   .venv/bin/python tools/run_pilot.py --srv6-repo ../substrate --n 20 --workers 4 --levels a0,a1,a1plus
   python3 tools/analyze.py
   ```
   Each cell redeploys a clean substrate, applies the seeded brownfield, runs the agent and
   verifies the outcome. Results go to `playground/results/pilot.json`.

Further details: `playground/README-NetAiBench.md` and the docstrings of the scripts in
`playground/tools/`.

## License

- Root and `playground/`: Apache License 2.0 (`LICENSE`, `NOTICE`,
  `playground/LICENSE-NetAiBench`, `playground/NOTICE-NetAiBench`).
- `substrate/`: GNU GPL v3.0 (`substrate/LICENSE.txt`, `substrate/README-substrate.md`).

## Citation

```bibtex
@inproceedings{bracciale2026anigamut,
  author    = {Bracciale, Lorenzo and Loreti, Pierpaolo and Mayer, Andrea and Salsano, Stefano and Henderickx, Wim},
  title     = {{ANI-Gamut}: Benchmarking Agent Reliability across the Gamut of Agent--Network Interface Abstractions},
  booktitle = {International Conference on Network and Service Management (CNSM)},
  address   = {Alcal\'a de Henares, Spain},
  year      = {2026}
}
```

## Project page

The site is a GitHub Pages site (Jekyll, `pages-themes/slate` remote theme) served from the
**`docs/`** folder: `_config.yml`, `index.md`, and `assets/`.
To publish: GitHub repo → *Settings → Pages → Deploy from a branch → `main` / `docs`*.

## Acknowledgment

This work has received funding from the Italian MUR PRIN NEWTON project.
