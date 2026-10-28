---
---

<p class="lead">LLM agents increasingly act on live networks: they read state, change configuration, and verify the result. A first-order question is usually left implicit: <strong>at which level of abstraction should the agent operate?</strong></p>

The same change can be presented to an agent as a raw device shell, as a typed declarative service request, or as an edit to a reconciled source of truth. These are very different contracts between the agent and the network. **ANI-Gamut** makes that level the variable we vary, holding the task, the model, and the observation interface fixed, and reads off reliability, safety, recovery, and cost.

<p class="quicklinks"><a href="#paper-and-resources">Paper (CNSM 2026)</a> &middot; <a href="https://arxiv.org/abs/2609.22723">Extended version (arXiv)</a> &middot; <a href="{{ '/preregistration.html' | relative_url }}">Analysis plan</a> &middot; <a href="https://netgroup.github.io/ani-gamut-talk-cnsm26/">Talk</a> &middot; <a href="#code">Code</a></p>

## The interface-abstraction spectrum

<div class="pills">
  <span class="pill good">A0</span>
  <span class="pill good">A1</span>
  <span class="pill good">A1+</span>
  <span class="pill conc">A2</span>
  <span class="pill good">A3-T</span>
  <span class="pill conc">A3-R</span>
  <span class="pill conc">A4</span>
</div>
<p class="legend">Green: implemented in ANI-Gamut &nbsp;&middot;&nbsp; grey: conceptual.</p>

<div class="spectrum">
  <div class="row"><div class="lvl g">A0</div><div class="desc">Raw device shell: an unbounded action space, no transactional semantics.</div></div>
  <div class="row"><div class="lvl g">A1</div><div class="desc">Bounded CLI wrapper: a generic guardrail (allowlist, management-plane protection) plus snapshot and manual rollback.</div></div>
  <div class="row"><div class="lvl g">A1+</div><div class="desc">A1 plus an ad-hoc anti-damage blocklist, used as an ablation against the structural levels.</div></div>
  <div class="row"><div class="lvl c">A2</div><div class="desc">Standardized model-driven configuration (NETCONF/YANG): typed, with candidate datastores and confirmed commit.</div></div>
  <div class="row"><div class="lvl g">A3-T</div><div class="desc">Typed transactional service intent: a workflow transaction manager applies the request with active validation and rollback.</div></div>
  <div class="row"><div class="lvl c">A3-R</div><div class="desc">Reconciled source of truth: a versioned desired state with drift detection and reconciliation.</div></div>
  <div class="row"><div class="lvl c">A4</div><div class="desc">Service intent combined with reconciliation; where commercial controllers already operate.</div></div>
</div>

## The playground

<div class="grid">
  <div class="card">
    <h3>A realistic brownfield</h3>
    <p>A single, densely populated multi-service substrate where many coexisting services share resources, so a careless change can shadow a prefix, reuse an identifier, or trip a global knob. This is where collateral damage actually arises, and where toy playgrounds hide it.</p>
  </div>
  <div class="card">
    <h3>The same task, at every level</h3>
    <p>One harness exposes an identical configuration task to the agent through a per-level adapter, on one emulated testbed. Released as open source so the community can reproduce, extend, and compare.</p>
  </div>
</div>

<figure>
  <img src="{{ '/assets/architecture.png' | relative_url }}" alt="ANI-Gamut architecture: a network operator states a configuration request over the human-agent interface (HAI) to the NMAA system, which acts on a brownfield network through the agent-network interface (ANI), whose abstraction level A0 to A4 is the controlled variable.">
  <figcaption>The system under test (an NMAA system) sits between the human&ndash;agent interface (HAI) and the agent&ndash;network interface (ANI); only the ANI level is varied, while the request, the model, and the observation are held constant.</figcaption>
</figure>

## The metric

Safe configuration is a **zero-tolerance** property: an agent that completes its task but silently breaks an unrelated, already-deployed service has caused an outage, not a success. The headline metric is therefore not mean task completion but the **rate of damage-free runs**, estimated with tail-aware statistics as the substrate is stressed by rising state density and injected faults. The hypothesis under test is that raising the interface level shrinks the agent's blast radius, a structural safety gain that ad-hoc guardrails approximate but do not match.

## Paper and resources

- **Paper.** L. Bracciale, P. Loreti, A. Mayer, S. Salsano, W. Henderickx, "ANI-Gamut: Benchmarking Agent Reliability across the Gamut of Agent&ndash;Network Interface Abstractions," *International Conference on Network and Service Management (CNSM 2026)*, Alcal&aacute; de Henares, Spain, October 2026.
- **Extended version** (full methodology, system architecture and appendices): [arXiv:2609.22723](https://arxiv.org/abs/2609.22723).
- **Hypotheses and analysis plan**: [as stated in Section VI of the paper]({{ '/preregistration.html' | relative_url }}), with the part of the plan executed in the pilot.
- **Talk**: CNSM 2026, Full Paper Session 2 "AI for Networks", 27 October 2026 &mdash; [slides](https://netgroup.github.io/ani-gamut-talk-cnsm26/).

## Code

The playground (composition manifest, scenario generator, harness) is released as open source in the [netgroup/ani-gamut](https://github.com/netgroup/ani-gamut) repository.

## How to cite

```bibtex
@inproceedings{bracciale2026anigamut,
  author    = {Bracciale, Lorenzo and Loreti, Pierpaolo and Mayer, Andrea and Salsano, Stefano and Henderickx, Wim},
  title     = {{ANI-Gamut}: Benchmarking Agent Reliability across the Gamut of Agent--Network Interface Abstractions},
  booktitle = {International Conference on Network and Service Management (CNSM)},
  address   = {Alcal\'a de Henares, Spain},
  year      = {2026}
}
```

## Acknowledgment

This work has received funding from the Italian MUR PRIN NEWTON project.
