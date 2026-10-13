# The MAS AI Risk Management Guidelines: what they require, what a tool can check, and what still needs people

**For Chief Risk Officers and Heads of Model Risk.** Every figure below is generated from
`results/summary.json`; nothing is typed by hand. Generated 2026-10-13 from airmkit
0.1.0 (0fbc770). Written by Claude Fable 5.1 from the author's results.

> airmkit is an independent open-source project, not affiliated with or endorsed by the Monetary Authority of Singapore. It is not legal, regulatory or compliance advice and is not a substitute for reading the Guidelines on Artificial Intelligence Risk Management (7 October 2026). Interpretations and all thresholds are the authors'.

## The obligation and its timetable

MAS issued the Guidelines on **7 October 2026**. They bind in two steps (§1.8). By **7 October
2027**: governance and named control functions (§3.3–§3.6); identification of AI use, including
AI embedded in services from material third-party providers (§4.2, fn21); an inventory whose
agentic entries carry identifiers, tools, components and guardrails (fn25); a use-case-level
materiality assessment over Impact, Complexity and Reliance (§4.12); and management of the
residual risk from AI you have *not* identified (§4.4, fn22). By **7 October 2028**: the
lifecycle controls of Section 5 and the competence of staff who *use* AI (§6.1), with high-risk
lifecycle controls expected sooner.

Two facts should shape the programme. **MAS prescribes no formula, metric or threshold** — not
for materiality, performance or guardrails (Response §7.19, §10.29) — so every number your
institution uses is its own to defend. And the final text, while more proportionate than the
draft, is **stricter on third-party, generative and agentic AI**: primary accountability stays
with you and you must be able to limit, suspend or replace a provider (§5.11); a vendor's
self-attestation generally does not close a transparency gap (Response §9.9); and guardrails
must be tested for *effectiveness* (§5.15, fn46).

## How much of it a tool can carry

We built the catalogue and the controls and measured the result. Of 51
expectation paragraphs, **45.1%** admit a fully automated check,
31.4% are semi-automatable — a tool confirms the artefact exists and is current, a
person judges adequacy — and 23.5% are documentary. The distribution matters more
than the total: **Section 4 is 84.6% automatable; Section 3 is
0.0%.** Tooling can carry the 2027 obligations and much less of the 2028
ones. On a 8-use-case fictional portfolio,
**93.1% of estimated effort is attestation and documentation**, against
6.8% a tool finishes unaided, and it is spread evenly across use cases
(Gini 0.0897) rather than concentrated in the riskiest. Headcount, not software, is the
binding constraint. *(Hours are published estimates, not measurements.)*

## Four findings to act on

1. **An agent raises the control set, not the tier.** 7 controls first
   bind when a use case becomes a tool-using agent — guardrail effectiveness testing, tool
   permissions, trace monitoring — but only 1 of 4 use cases
   moved up a tier, because tier is driven by consequence. A review process keyed on tier will
   miss the agent step; key it on the control set.
2. **Guardrail reports without a benign control set are unfalsifiable.** On a local model, attack
   success fell from 75.0% unguarded to 6.2% with a layered defence —
   and the same defence refused **50.0% of ordinary in-scope requests**.
   Against a pre-registered joint criterion, 0 of 5
   patterns passed. Require over-refusal beside attack success in every guardrail report you
   accept, internal or vendor.
3. **ISO 42001 and NIST alignment leave governance work, not agent work.** No framework fully
   covers more than 49.0% of expectations, and the ISO + NIST + EU
   AI Act union leaves **35.3% with no full mapping**. The residue is the
   applicability test and basic regime (§2.2, §2.5), board responsibilities (§3.4),
   identification and shadow AI (§4.1, §4.4), materiality arbitration (§4.13), third-party
   accountability (§5.11) and independent validation scope (§5.20) — not the agent clauses,
   which the NIST Generative AI Profile covers well. If you are certified, that list is the
   remaining work.
4. **Proportionality scales rigour, not volume.** Critical-tier use cases need
   91.4 evidence items on average against
   92.0 at Medium. The artefacts are the same; the depth of review and
   the seniority of sign-off change. Budget reviewers, not document counts.

## The next quarter

Build the inventory first: it is the 2027 obligation, the most automatable, and every later
control depends on it. Write down the materiality method and the reason behind each signal,
since MAS will not supply one. Run a shadow-AI sweep and record the residual-risk *decision*,
not only the findings. Change the guardrail test template to report over-refusal beside attack
success. Re-scope third-party assessments to the eight §5.11 considerations and replace
self-attestation with independent assessment wherever the provider is material.

## Reproduce or dispute it

```bash
pip install airmkit
airm clauses                                # the clause catalogue with effective dates
airm assess -r ai-inventory.yaml            # materiality, with the reason for every score
airm check  -r ai-inventory.yaml            # pass / fail / needs-attestation / not-applicable
airm report -r ai-inventory.yaml -o pack/   # the full audit pack
```

Every control cites the paragraph it serves and every automatability class carries a written
rationale, so a single judgement can be disputed without rejecting the method. The worked
example, the five pre-registered experiments and all 7 refuted hypotheses are
in the repository, and the full study is at <https://thanatchon36.github.io/airmkit/paper/>.
**<https://github.com/thanatchon36/airmkit>**
