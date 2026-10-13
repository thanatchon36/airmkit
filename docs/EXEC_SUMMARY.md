# MAS AI Risk Management Guidelines: what they require, what a tool can check, what still needs people

**For CROs and Heads of Model Risk.** Every number is generated from `results/summary.json`;
nothing here is typed by hand. Generated 2026-10-13 from airmkit 0.1.0
(2481930).

> airmkit is an independent open-source project, not affiliated with or endorsed by the Monetary Authority of Singapore. It is not legal, regulatory or compliance advice and is not a substitute for reading the Guidelines on Artificial Intelligence Risk Management (7 October 2026). Interpretations and all thresholds are the authors'.

## The deadlines

MAS issued the Guidelines on **7 October 2026**, phased (§1.8): **Sections 3-4 by 7 Oct 2027** -
governance and control functions, AI identification including embedded third-party AI (§4.2,
fn21), the inventory with agent attributes (fn25), use-case materiality over Impact, Complexity
and Reliance (§4.12), and residual risk from *unidentified* AI kept within appetite (§4.4, fn22).
**Sections 5-6 by 7 Oct 2028** - the lifecycle controls and the competence of staff *using* AI
(§6.1), with high-risk lifecycle controls expected sooner.

Two things to plan around. **MAS prescribes no formula, metric or threshold** for materiality,
performance or guardrails (Resp §7.19, §10.29): every number you use is yours to defend. And the
final text, while more proportionate than the draft, is **tighter on third-party AI and on
generative AI and agents**: you retain primary accountability and must be able to limit, suspend
or replace a provider (§5.11), vendor self-attestation generally does not close a transparency gap
(Resp §9.9), and guardrails must be tested **for effectiveness** (§5.15, fn46).

## What tooling covers

Of 51 expectation paragraphs, **45.1%** admit a fully
automated check, 31.4% are semi-automatable (a tool confirms the artefact exists and
is current; a person judges adequacy) and 23.5% are documentary. The distribution
matters more: **Section 4 is 84.6% automatable, Section 3 is
0.0%.** Tooling can carry the 2027 obligations and much less of the 2028
ones. On our 8-use-case fictional portfolio,
**93.1% of estimated effort is attestation and documentation** against
6.8% a tool finishes unaided, spread evenly across use cases (Gini
0.0897). Headcount, not tooling, is the binding constraint. *(Hours are our estimates from a
published table, not measurements.)*

## Four findings worth acting on

1. **A system becoming an agent raises the control set, not the tier.**
   7 controls first bind at the agent step - guardrail effectiveness
   testing, tool permissions, trace monitoring - but only 1 of
   4 use cases gained a tier, because tier is dominated by consequence. Review the
   control set, not the label.
2. **Guardrail tests against attacks only will mislead you.** Attack success fell from
   75.0% unguarded to 6.2% layered on a local model - and the same
   layered defence refused **50.0% of benign in-scope requests**. Against
   our pre-registered joint criterion, 0 of 5 patterns
   passed. Require a benign control set in every guardrail report you accept, internal or vendor.
3. **ISO 42001 and NIST alignment leaves governance work, not agent work.** No framework fully
   covers more than 49.0% of expectations; the ISO + NIST + EU AI Act
   union leaves **35.3% with no full mapping**. The residue is the
   applicability test and basic regime (§2.2, §2.5), board responsibilities (§3.4), identification
   and shadow AI (§4.1, §4.4), materiality arbitration (§4.13), third-party accountability (§5.11)
   and independent validation scope (§5.20) - not the agent clauses, which the NIST Generative AI
   Profile covers well. If you are certified, that list is your remaining work.
4. **Proportionality scales rigour, not volume.** Critical-tier use cases need
   91.4 evidence items on average against
   92.0 for Medium. The same artefacts are required; what changes is the
   depth of review and who signs.

## Next quarter

Build the inventory first - it is the 2027 obligation, the most automatable, and everything else
depends on it. Write down your materiality method and the reason behind each signal, since MAS
will not supply one. Run a shadow-AI sweep and record the residual-risk *decision*, not only the
findings. Change your guardrail test template to report over-refusal beside attack success.
Re-scope third-party assessments to the eight §5.11 considerations.

## Reproduce or dispute it

```bash
pip install airmkit
airm clauses                                # clause catalogue with effective dates
airm assess -r ai-inventory.yaml            # materiality, with reasons for every score
airm check  -r ai-inventory.yaml            # pass / fail / needs-attestation / not-applicable
airm report -r ai-inventory.yaml -o pack/   # the full audit pack
```

Every control cites the paragraph it serves and every automatability class carries a written
justification, so one judgement can be disputed without rejecting the method. The worked example,
the five experiments, the pre-registered thresholds and all 7 refuted
hypotheses are in the repository: **<https://github.com/thanatchon36/airmkit>**
