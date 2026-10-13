# Cookbook

Recipes in the order a team usually needs them. Every snippet runs against the shipped worked
example, so you can try it before touching your own register.

## Gate CI on control failures

`airm check` exits `1` on a genuine automated failure and `0` when the only open items are
attestations, so it can gate a pipeline without punishing teams for work that is a human's to do.

```yaml
# .github/workflows/ai-governance.yml
- run: pip install airmkit
- run: airm check --register ai-inventory.yaml --trail evidence/trail.jsonl
- run: airm check --register ai-inventory.yaml --institution
```

Add `--json results.json` and upload it as an artefact if you want the outcomes in your GRC tool.

## See why a use case is rated the way it is

```bash
airm assess -r examples/synthetic_bank/ai-inventory.yaml -u kyc-document-agent --explain
```

Every dimension prints the signals that fired and the paragraph each derives from. If you disagree
with a signal, you are disagreeing with a line of YAML, which is the point.

## Fork the rubric

```bash
airm init --rubric-out rubric.yaml      # editable copy of the defaults
$EDITOR rubric.yaml                     # change weights, thresholds, the impact gate
airm assess -r ai-inventory.yaml --rubric rubric.yaml
```

Keep the `clause` field on every signal you add. A signal with no paragraph behind it is a house
view, not a MAS expectation, and the gap analysis will treat it as one.

## Find AI nobody declared

```bash
airm scan . --min-confidence high --out candidates.yaml
```

Then triage `candidates.yaml` by hand into the register. §4.4 and fn22 ask for the *residual risk*
from unidentified AI to be managed, so record the decision as well as the findings:

```bash
airm evidence shadow-ai-sweep -a "model.risk@bank" \
  --item "scan-report=evidence/scan-2027-01.json" --outcome pass
```

## Audit an agent's tool use against its approved scope

Serves §5.23(a) with fn25: did the agent only use the tools its inventory entry approves?

```python
from airm.evals import tool_scope_audit
from airm.inventory import Register

register = Register.load("examples/synthetic_bank/ai-inventory.yaml")
use_case = register.get("kyc-document-agent")

observed = ["ocr_extract", "registry_lookup", "email_send"]   # names pulled from your traces
audit = tool_scope_audit(use_case, observed, calls=412)

print(audit.unapproved)   # ['email_send'] — used but outside the approved scope
print(audit.unused)       # approved but never used: scope to tighten
print(audit.clauses)      # the paragraphs this audit serves
```

Tool names from traces are compared as strings and never resolved or invoked.

## Map an eval harness result to a control

The toolkit does not run evaluations; it reads what your harness already produced and maps it to
the control that needs it (§5.14-§5.15).

```python
from airm.evals import from_inspect, from_garak, from_ragas

robustness = from_garak("garak-report.jsonl", use_case_id="customer-service-chatbot")
faithfulness = from_ragas("ragas.json", use_case_id="policy-rag-assistant")

print(robustness.failure_modes_covered)   # mapped to the fn46 failure modes
print(faithfulness.passed)                # against the thresholds you pass in
print(faithfulness.model, faithfulness.model_digest, faithfulness.seed)  # recorded for §5.17
```

Adapters exist for `inspect-ai`, `promptfoo`, `garak`, `ragas` and `deepeval`. Store the result as
an evidence record so the control check can find it.

## Measure guardrail effectiveness, honestly

§5.15 fn46 asks for guardrail *effectiveness* to be tested. The probe runner ships 20 probes
across jailbreak, indirect injection, PII leakage and policy evasion — plus a benign in-scope
control set, because a guardrail that refuses everything scores perfectly on attacks.

```python
from airm.evals.probes import GuardrailPattern, MockBackend, run_suite

result = run_suite(MockBackend(), patterns=[GuardrailPattern.FILTER, GuardrailPattern.LAYERED])
for run in result.runs:
    rate, successes, trials = run.asr()
    refusal, refusals, benign = run.over_refusal()
    print(run.pattern, f"ASR {rate:.1%} ({successes}/{trials})",
          f"over-refusal {refusal:.1%} ({refusals}/{benign})",
          "meets High tier:", run.meets_tier("High"))
```

`meets_tier` tests the **upper** Wilson bound against the proposed per-tier limit, so a small
sample cannot manufacture a pass: 0 successes in 16 trials still fails the High tier. Swap
`MockBackend()` for `OllamaBackend("qwen3.5:0.8b")` to measure a real local model. Read
the `OllamaBackend` docstring first: it documents two measurement defects we hit, including an
empty-completion bug that produced a false 0% attack success rate.

## Verify evidence has not changed

```bash
airm evidence --verify -t examples/synthetic_bank/evidence/trail.jsonl
```

Reports a broken hash chain and any evidence file whose digest no longer matches what was attested.

## Answer "we already hold ISO 42001 — what is left?"

```bash
airm crosswalk --holding iso_42001,nist_ai_rmf
```

Prints the expectations with no full mapping. On our crosswalk that residue is governance
machinery and MAS-specific proportionality, not the agent clauses.

## Produce the audit pack

```bash
airm report -r examples/synthetic_bank/ai-inventory.yaml \
  --vendors examples/synthetic_bank/third-party-assessments.yaml \
  --trail examples/synthetic_bank/evidence/trail.jsonl \
  -o audit-pack/ --docx
```

Nine documents, starting with `00-board-summary.md`. The pack also writes `summary.json`, which is
the machine-readable version of every count in it.

## Validate files without Python

```bash
check-jsonschema --schemafile schemas/ai-inventory-register.schema.json ai-inventory.yaml
```

All 20 formats are exported as JSON Schema; regenerate with `airm schemas`.

## Reproduce the study

```bash
make quick        # lint, fast tests, worked example — under 5 minutes
make reproduce    # every table and figure in the paper, no hosted API
```

`make reproduce` ends by printing a `git diff --stat` of `results/`, `schemas/`, `paper/` and
`docs/`. An empty diff means your clone reproduces the published run.
