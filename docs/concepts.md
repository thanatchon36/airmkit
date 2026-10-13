# Concepts

Five objects, in the order the Guidelines ask for them.

## 1. The clause catalogue (`airm.catalog`)

Every paragraph of the Guidelines as data: id, section, heading, a summary in the authors' words,
whether it is an expectation, a definition or guidance, who it applies to, its effective date and
tags (`genai`, `agent`, `third-party`, `inventory`, `materiality`, `human-oversight`, …).
Footnotes are included where they carry a requirement — fn25 (agent inventory attributes), fn22
(shadow-AI controls), fn46 (GenAI failure modes) and 26 others.

```python
from airm.catalog import load_catalogue

catalogue = load_catalogue()
print(len(catalogue), "paragraphs", len(catalogue.expectations()), "expectations")
print(catalogue["5.15"].summary, catalogue["5.15"].effective)
```

Nothing else in the toolkit may cite a paragraph the catalogue does not contain; a test enforces
it. That is the whole defence against a control catalogue that drifts into invention.

## 2. The inventory (`airm.inventory`)

A `Register` of `UseCase` entries, matching the attributes of §4.7 and fn24. A use case that is
tool-using carries an `AgentExtension` with the fn25 attributes: agent identifier, approved tools,
systems accessible, permissions, components, guardrails, human checkpoints, step limits, whether
it can initiate external actions, and whether traces are logged.

Two things to know:

- **Autonomy and agency are validated together.** Setting `autonomy` to an agentic level without
  an `AgentExtension` is a validation error, and so is the reverse. Build the object in one call;
  you cannot mutate the two fields in sequence.
- **`airm scan` produces candidates, not entries.** Shadow-AI discovery (§4.4, fn22) is a
  heuristic over imports, endpoints, MCP configs and SaaS references. Its output is data to be
  triaged, never configuration to be trusted.

## 3. Materiality (`airm.materiality`)

A YAML rubric scores **Impact**, **Complexity** and **Reliance** (§4.12(a)-(c)) from 23 signals,
each citing the paragraph it derives from, and combines them into an **inherent tier** (Low,
Medium, High, Critical) and a **residual tier** after declared mitigations. Every score carries
its reasons, so an assessment can be argued with rather than only accepted.

!!! note "The rubric is a proposal"
    MAS prescribes no materiality methodology (Response to Feedback §7.19). The default rubric is
    the authors'. Fork it: `airm assess --rubric my-rubric.yaml`.

Two default behaviours worth knowing before you fork:

- **The impact gate.** Complexity and Reliance can raise the tier at most one level above Impact.
  An internal research assistant does not become Critical because it uses an LLM.
- **No generative-AI use case can be rated Low**, because GenAI sets Complexity to High and the
  gate then permits one level above Impact. This is a consequence of the defaults, reported as a
  finding rather than tuned away.

## 4. Controls and outcomes (`airm.controls`)

Each control carries its clause references, applicability by tier and scope, the evidence items it
requires, an optional automated check, and an **automatability class**:

| Class | Meaning | Best outcome |
|---|---|---|
| `auto` | A deterministic function of the entry and its evidence decides the outcome | `PASS` |
| `semi` | The artefact's presence and currency are checkable; adequacy is not | `NEEDS_ATTESTATION` |
| `doc` | Organisational or judgemental; no artefact to inspect | `NEEDS_ATTESTATION` |

!!! important "A `semi` control never reports PASS"
    When a `semi` control's automated check succeeds, the outcome is `NEEDS_ATTESTATION`: the
    toolkit found the artefact and confirmed it is current, and a person must judge whether it is
    adequate. Read the attestation count as a work queue, not a failure count. `airm check` exits
    non-zero only on a genuine `FAIL`, because a pipeline that failed on attestations would teach
    people to suppress them.

Scope matters too: most controls are evaluated per use case, seven are evaluated once per
institution (the §3.3-§3.5 control functions, §4.1-§4.4 identification process).

## 5. Evidence (`airm.monitor`)

An append-only JSONL trail where each record carries the hash of the previous one, plus a digest
of every evidence file it points at. `airm evidence --verify` detects both a broken chain and a
file that changed after it was attested. This serves §5.23(d) and §5.17: an auditor can tell that
the evidence is the evidence that was signed off.

Incidents have their own schema, following the §5.23(b) definition in fn20.

## How they compose

```
airm scan      →  candidate entries        (§4.2, §4.4)
airm init      →  register + rubric
airm assess    →  tiers, with reasons      (§4.10-§4.13)
airm check     →  outcomes, with evidence  (§5.2-§5.26)
airm evidence  →  hash-chained trail       (§5.23(d))
airm report    →  the audit pack           (§3.4, §4.5, §5.2, §1.8)
airm gap       →  what is missing, by effective date
airm crosswalk →  what ISO/NIST/EU already cover
```

See the [cookbook](cookbook.md) for each of these as a worked snippet.
