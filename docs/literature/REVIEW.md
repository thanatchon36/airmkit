# Literature review

Scope: the regulatory and academic material that an implementer of the MAS Guidelines on AI Risk
Management (MAS-AIRM, 7 Oct 2026) needs in order to turn the text into controls, and the evidence base
for the five research questions in `docs/RESEARCH_QUESTIONS.md`. Citation keys refer to `refs.bib`.
Where a claim rests on a document we could not download as a primary source it is marked `[UNVERIFIED]`.

## 1. MAS primary documents

**MAS-AIRM (2026)** [@mas2026airm] is a principles-based, 30-page document with 65 numbered paragraphs
and 51 footnotes. Fifty-one paragraphs are expectations ("should"), the rest scope, definitions and
context (see `src/airm/catalog/mas_airm_2026.yaml`). It is deliberately non-prescriptive about metrics,
thresholds and the aggregation of its three materiality dimensions (Response §7.19, §10.28). Its
distinctive features relative to earlier MAS material are (i) a use-case-anchored risk materiality
assessment with Impact / Complexity / Reliance (§4.12), (ii) an inventory expectation with named
attributes (§4.7) extended to agents (fn25), (iii) explicit treatment of shadow AI and embedded AI
(§4.2, §4.4), (iv) guardrail-effectiveness testing for GenAI and agents (§5.15), and (v) third-party
AI accountability with a limit / suspend / replace expectation (§5.11).

**Response to Feedback (2026)** [@mas2026response] is the authoritative gloss. It settles several
points that the Guidelines leave open: high-risk triggers key on *inherent* materiality (§7.21);
evaluation is at use-case level (§10.30); vendor self-attestations are not acceptable substitutes for
transparency (§9.9); contingency plans are required only for high-risk use cases (§10.70); no AI-specific
incident reporting regime is introduced (§10.69). `docs/WHAT_CHANGED.md` lists 36 changes.

**Consultation paper P017-2025 (2025)** [@mas2025consult] contained the draft text plus an Annex with
a workflow-dependence applicability test that was dropped in the final version.

**Information Paper on AI Model Risk Management (Dec 2024)** [@mas2024infopaper] reports good practices
from a thematic review of banks. Its chapter structure (governance; identification, inventory,
materiality; development, validation, deployment, monitoring, change; GenAI; third-party AI) is the
template the Guidelines follow, and it supplies the concrete practices (e.g., materiality tiers used by
banks, validation scopes) that the Guidelines abstract away. The toolkit's default rubric levels borrow
from the Info Paper's observed practice rather than from the Guidelines, which name dimensions but not
levels.

**FEAT Principles (2018)** [@mas2018feat] remain in force (§1.2) and are the named reference for
"fair" outcomes (fn35). The 14 principles are organised as Fairness (justifiability; accuracy and
bias), Ethics, Accountability (internal; external) and Transparency. They are the source of the
crosswalk's FEAT column.

**Veritas (2021–2023)** [@mas2022veritas3; @mas2022veritas3a; @mas2022veritas3c; @mas2023veritas5]
provides assessment methodologies and an open-source fairness toolkit (`veritastool`, Apache-2.0) for
tabular models. Veritas Document 3A's fairness methodology (define fairness objectives → choose
metric → measure → mitigate → document) is the pattern `airm.evals.fairness` follows; Document 3C's
transparency questions inform the transparency control's evidence list. Veritas pre-dates LLMs and
has no guidance on generative or agentic systems.

## 2. International frameworks used in the crosswalk

**NIST AI RMF 1.0 (2023)** [@nist2023airmf] organises practice into Govern, Map, Measure, Manage with
72 subcategories. MAS-AIRM footnotes 31 and 51 cite it directly. The **Generative AI Profile
(NIST AI 600-1, 2024)** [@nist2024genai] adds 12 GenAI risk categories (e.g., confabulation,
information security, value-chain and component integration) and ~200 suggested actions, which is the
most granular public source for GenAI controls and maps well onto MAS-AIRM §5.15/fn46.

**ISO/IEC 42001:2023** [@iso2023_42001] is a certifiable AI management-system standard. Its Annex A
controls (A.2–A.10) cover policy, roles, resources, impact assessment, lifecycle, data, information for
interested parties, use, and third-party relationships. The Response (§9.7–9.9) explicitly contemplates
ISO 42001 certification of *vendors* as evidence. **ISO/IEC 23894:2023** [@iso2023_23894] (AI risk
management guidance) and **ISO/IEC 22989:2022** [@iso2022_22989] (terminology; cited in MAS-AIRM fn27)
supply vocabulary.

**EU AI Act (Regulation (EU) 2024/1689)** [@eu2024aiact] imposes obligations on providers and
deployers of high-risk systems (Arts. 9 risk management, 10 data governance, 11–12 documentation and
logging, 13 transparency, 14 human oversight, 15 accuracy/robustness/cybersecurity, 17 QMS, 26 deployer
obligations, 72 post-market monitoring). Credit scoring and life/health insurance pricing are listed
high-risk uses (Annex III §5), so the overlap with MAS-AIRM §5.6–5.8 is substantial. The Act is
binding law with conformity assessment; MAS-AIRM is supervisory guidance.

## 3. Comparable financial-sector guidance

- **US Fed SR 11-7 / OCC 2011-12** [@fed2011sr117] is the ancestor of all "model risk management" (MRM)
  text: model inventory, validation (conceptual soundness, ongoing monitoring, outcomes analysis),
  independence and effective challenge, governance. MAS-AIRM §5.17–5.19 and §5.24 are recognisably
  SR 11-7 concepts restated for AI.
- **Bank of England PRA SS1/23 (2023)** [@pra2023ss123] sets five principles (model identification and
  classification; governance; development, implementation and use; independent validation; model risk
  mitigants) with a *model tiering* requirement that parallels MAS-AIRM §4.10–4.13.
- **HKMA** has issued principles on consumer protection in the use of GenAI (2024) [@hkma2024genai]
  and a circular on the use of AI in monitoring suspicious activities; **BNM** (Malaysia) consulted on
  AI risk management for financial institutions in 2025 `[UNVERIFIED: text not acquired]`. These are the
  natural next crosswalk targets (`CONTRIBUTING.md`).
- **BIS FSI Insights No. 63 (2024)** [@bis2024fsi63] surveys AI regulation across jurisdictions and
  identifies inventories, materiality tiering and third-party dependency as the common supervisory
  building blocks.
- **FSB (2024)** [@fsb2024ai] highlights third-party dependency and concentration as the financial-stability
  channel, which MAS-AIRM §1.10(d), §5.11(c) and fn18 echo.

## 4. Academic literature by MAS-AIRM theme

### 4.1 Agent governance and visibility (§1.11, fn25, §5.9, §5.23(a))
Chan et al. [@chan2023harms] taxonomise harms from increasingly agentic systems; Chan et al.
[@chan2024visibility] argue for **agent identifiers, real-time monitoring and activity logs** as
visibility measures, which is almost exactly fn25 + §5.23(a)(d). Shavit et al. [@shavit2023agentic]
(OpenAI) propose practices for governing agentic systems including scoped permissions, default
behaviours and attributability. Kapoor et al. [@kapoor2024agents] show agent benchmarks conflate
accuracy with cost and lack holdout sets, cautioning against naive use of benchmark scores as
"evaluation measures" under §5.14(a). Ruan et al. [@ruan2024toolemu] (ToolEmu) and Debenedetti et al.
[@debenedetti2024agentdojo] (AgentDojo) provide sandboxed environments for measuring unsafe tool use
and indirect prompt injection in agents; Zhan et al. [@zhan2024injecagent] benchmark indirect injection
specifically against tool-integrated agents.

### 4.2 Guardrail evaluation and adversarial robustness (§5.15, fn46, §5.22(b))
Greshake et al. [@greshake2023indirect] introduced indirect prompt injection; Perez & Ribeiro
[@perez2022ignore] direct injection; Wei et al. [@wei2023jailbroken] explain jailbreaks as competing
objectives and mismatched generalisation; Zou et al. [@zou2023gcg] show transferable adversarial
suffixes; Chao et al. [@chao2023pair] automate jailbreaks with an attacker LLM. HarmBench
[@mazeika2024harmbench] standardises red-team evaluation. On the defence side, Llama Guard
[@inan2023llamaguard] and NeMo Guardrails [@rebedea2023nemo] are the canonical classifier- and
rail-based guardrail patterns; garak [@derczynski2024garak] is the open-source LLM vulnerability
scanner the toolkit adapts. OWASP's Top 10 for LLM Applications [@owasp2025llm] and MITRE ATLAS
[@mitre2024atlas] give the threat vocabulary used in `airm.controls` security controls.

### 4.3 LLM evaluation validity (§5.14, §5.17)
HELM [@liang2022helm] established multi-metric, scenario-based evaluation; Zheng et al.
[@zheng2023judge] quantify LLM-as-judge agreement with humans (~80 %) and its biases (position,
verbosity, self-enhancement), which matters when §5.14(a) thresholds are computed by a judge model.
RAGAS [@es2023ragas] and FActScore [@min2023factscore] operationalise faithfulness and factual
precision for RAG; Ji et al. [@ji2023hallucination] survey hallucination. Inspect [@aisi2024inspect]
(UK AI Security Institute) is the eval harness whose log format the toolkit reads. Weidinger et al.
[@weidinger2022taxonomy] give the risk taxonomy that NIST AI 600-1 and fn46 compress.

### 4.4 Documentation, auditability and accountability (§5.17, §5.21, §5.23(d))
Model Cards [@mitchell2019modelcards] and Datasheets [@gebru2021datasheets] are the de-facto templates
for §5.17(a)–(f); Raji et al. [@raji2020audit] define the internal audit framework (scoping, mapping,
artefact collection, testing, reflection) that §5.18–5.21 presuppose.

### 4.5 Fairness (§5.7–5.8)
Hardt et al. [@hardt2016equality] (equalised odds / equal opportunity) and the Barocas–Hardt–Narayanan
text [@barocas2023fairml] cover the metric landscape; Veritas 3A chooses among them for credit and
insurance. fn36's proxy requirement is the "proxy discrimination" problem these sources formalise.

### 4.6 Model risk management for ML
The SR 11-7 lineage is reinterpreted for ML in the Info Paper [@mas2024infopaper] and PRA SS1/23
[@pra2023ss123]; the academic MRM literature is thin and mostly practitioner-authored. Bommasani
et al. [@bommasani2021foundation] frame the foundation-model supply chain that makes §5.11(b)–(c)
(supply chain, concentration) necessary.

## 5. Gap table: MAS expectations without an established implementation pattern

| MAS-AIRM clause | Expectation | Established pattern? | Closest available | Gap |
|---|---|---|---|---|
| §4.4, fn22 | Keep residual risk from *unidentified* AI within appetite | **No** | DLP/CASB logs; SBOM-style scanning | No standard for measuring shadow-AI coverage; `airm scan` is a repo-level heuristic only |
| §4.2, fn21 | Identify embedded AI in material third-party services | **No** | Vendor questionnaires; AI BOM proposals | No machine-readable vendor AI disclosure format |
| §4.12 | Combine Impact / Complexity / Reliance into a tier | Partial | PRA SS1/23 tiering; bank practice in Info Paper | No public rubric; this toolkit proposes one (RQ2) |
| fn25 | Agent attributes: tools/systems accessible, guardrails | Partial | Chan et al. 2024 visibility; MCP/tool manifests | No inventory schema standard; proposed in `schemas/` |
| §5.15, fn46 | Test *effectiveness* of guardrails | Partial | HarmBench, garak, AgentDojo | No accepted threshold per risk tier (RQ3) |
| §5.23(a) | Monitor agent reasoning, actions, tools | Partial | OpenTelemetry GenAI semantic conventions; tracing | No link from traces to *approved scope* checks; toolkit adds tool-scope audit |
| §5.23(d) | Prompt/response logging with model version and reasoning | Partial | Tracing frameworks | Retention, privacy and tamper-evidence not standardised; toolkit uses hash-chained JSONL |
| §5.25(a),(c) | Significance of changes incl. prompt/model-version changes and auto-updates | **No** | Software change management | No agreed taxonomy of "significant" LLM changes; default classes proposed (I-10) |
| §5.11(a) | Independent certification/assessment of AI vendors | Partial | ISO 42001 certification; SOC 2 | ISO 42001 does not test model behaviour; coverage of "key risks from AI use" unverified |
| §5.17 | Reproduce the *evaluation process* for non-deterministic models | Partial | Seeded, cached eval runs | No convention for recording sampling parameters and model digests in evidence; toolkit records both |
| §5.3 | Tested kill-switch protocols for high-risk AI | **No** | BCP/DR testing | No evidence format for "kill switch tested"; toolkit treats as attestation |
| §5.9 | Automation bias and decision fatigue | **No** | HCI literature | No operational metric; attestation only |
| §6.1–6.2 | Competence of AI *users* | **No** | Training completion records | Attestation only |

The gap table drives RQ1 (which clauses can be automated) and `docs/FUTURE_WORK.md`.
