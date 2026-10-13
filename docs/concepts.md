# Concepts

The toolkit is built around five objects, in the order the Guidelines ask for them. Each one
exists because a paragraph of the text requires it, and each carries the paragraph that does.

## 1. The clause catalogue — `airm.catalog`

Every paragraph of the Guidelines as data: identifier, section, heading, a summary of at most
forty words in the authors' own words, a kind (expectation, definition, scope, context or
guidance), who it applies to, its effective date under §1.8, and tags such as `genai`, `agent`,
`third-party`, `inventory`, `materiality` and `human-oversight`. Footnotes are included where
they carry a requirement: fn25 (agent inventory attributes), fn22 (controls for unidentified
AI), fn46 (generative-AI failure modes) and 26 others.

```python
from airm.catalog import load_catalogue

catalogue = load_catalogue()
print(len(catalogue), "paragraphs;", len(catalogue.expectations()), "expectations")
print(catalogue["5.15"].summary, catalogue["5.15"].effective)
```

Nothing else in the toolkit may cite a paragraph the catalogue does not contain; a test enforces
it. That rule is the only mechanical defence against a control catalogue that drifts into
invention, and it is why every citation in the paper can be traced to a line of YAML and from
there to a page of the primary PDF.

## 2. The inventory — `airm.inventory`

A `Register` of `UseCase` entries carrying the attributes of §4.7 and fn24. A tool-using use
case adds an `AgentExtension` with the fn25 attributes: agent identifier, approved tools,
systems accessible, permissions, components, guardrails, human checkpoints, a step limit,
whether the agent can initiate external actions, and whether its traces are logged.

Two behaviours are easy to trip over:

- **Autonomy and agency are validated together.** An agentic autonomy level without an
  `AgentExtension` is a validation error, and so is the reverse. Build the object in one call;
  the two fields cannot be mutated in sequence.
- **`airm scan` produces candidates, not entries.** Shadow-AI discovery (§4.4, fn22) is a
  heuristic over imports, endpoints, MCP configurations and SaaS references. Its output is data
  to be triaged, never configuration to be trusted, and a clean scan means the scanner found
  nothing, which is not the same as there being nothing.

## 3. Materiality — `airm.materiality`

A YAML rubric scores **Impact**, **Complexity** and **Reliance** (§4.12(a)–(c)) from 23 signals,
each citing the paragraph it derives from, and combines them into an **inherent tier** — Low,
Medium, High or Critical — and a **residual tier** after declared mitigations. Every score
carries its reasons, so an assessment can be argued with rather than only accepted.

!!! note "The rubric is a proposal"
    MAS prescribes no materiality methodology (Response to Feedback §7.19). The default rubric is
    the authors'. Fork it with `airm init --rubric-out rubric.yaml` and
    `airm assess --rubric rubric.yaml`.

Two default behaviours are worth knowing before you fork:

- **The impact gate.** The tier is the highest of the three dimensions, but Complexity and
  Reliance may raise it at most one level above Impact. The gate implements Response §7.9
  (Complexity is not a standalone driver) and §7.5 (anchor on the consequences of failure), and
  it is why an internal research assistant does not become Critical for using an LLM.
- **No generative-AI use case can be rated Low.** GenAI sets Complexity to High, and the gate
  then permits one level above Impact. This is a consequence of the defaults, reported in the
  paper as a finding rather than tuned away.

## 4. Controls and outcomes — `airm.controls`

Each control carries its clause references, applicability by inherent tier and by scope, the
evidence items it requires, an optional automated check, and an **automatability class**:

| Class | Meaning | Best possible outcome |
|---|---|---|
| `auto` | A deterministic function of the entry and its evidence decides the outcome | `PASS` |
| `semi` | The artefact's presence and currency are checkable; its adequacy is not | `NEEDS_ATTESTATION` |
| `doc` | Organisational or judgemental; there is no artefact to inspect | `NEEDS_ATTESTATION` |

!!! important "A `semi` control never reports PASS"
    When a `semi` control's automated check succeeds, the outcome is `NEEDS_ATTESTATION`: the
    toolkit found the artefact and confirmed it is current, and a person must judge whether it
    is adequate. Read the attestation count as a work queue, not a failure count. `airm check`
    exits non-zero only on a genuine `FAIL`, because a pipeline that failed on attestations
    would teach people to suppress them.

Scope matters too. Most controls are evaluated per use case; seven are evaluated once per
institution — the §3.3–§3.5 control functions and the §4.1–§4.4 identification process. The
paper's RQ1 measures how the classes are distributed across the Guidelines: 84.6% of Section 4
expectations are `auto`, none of Section 3's are.

## 5. Evidence — `airm.monitor`

An append-only JSONL trail in which each record carries the hash of the previous one and a
digest of every evidence file it points at. `airm evidence --verify` detects both a broken chain
and a file that changed after it was attested, which is what §5.23(d) and §5.17 need an auditor
to be able to do: confirm that the evidence on the table is the evidence that was signed off.

Incidents have their own schema, following the fn20 definition in §5.23(b).

## How they compose

```
airm scan      →  candidate entries           (§4.2, §4.4)
airm init      →  register + rubric
airm assess    →  tiers, with reasons         (§4.10–§4.13)
airm check     →  outcomes, with evidence     (§5.2–§5.26)
airm evidence  →  hash-chained trail          (§5.23(d))
airm report    →  the audit pack              (§3.4, §4.5, §5.2, §1.8)
airm gap       →  what is missing, by effective date
airm crosswalk →  what ISO / NIST / EU already cover
airm schemas   →  every format as JSON Schema
```

The [cookbook](cookbook.md) walks through each of these with a snippet that was run against the
shipped example.
