# What changed between the consultation draft (Nov 2025) and the final Guidelines (7 Oct 2026)

Sources: consultation paper P017-2025 (`docs/sources/mas_consultation_paper_P017-2025_2025-11-13.pdf`,
Section 6 "Proposed Guidelines" and Annex), final Guidelines (`docs/sources/mas_airm_guidelines_2026-10-07.pdf`)
and MAS' Response to Feedback (`docs/sources/mas_response_to_feedback_P017-2025_2026-10-07.pdf`, cited as *Resp §n*).
Paragraph numbers: **D-x.y** = draft, **§x.y** = final. The draft had five sections; the final inserts a new
Section 2, so draft Sections 2–5 became final Sections 3–6.

Legend: **T** tightened (new or stricter expectation) · **E** eased (relaxed, made optional or proportionate) ·
**R** removed · **C** clarified / restructured without changing substance · **N** new.

## 1. Headline changes

| # | Change | Type | Final | Draft | Basis |
|---|---|---|---|---|---|
| 1 | Transition: single 12-month period → phased. Sections 3–4 by **7 Oct 2027**, Sections 5–6 by **7 Oct 2028**; high-risk lifecycle controls "as soon as possible". | E | §1.8 | CP §4.7 | Resp §13.4–13.6 |
| 2 | Applicability test rewritten. "AI as an integrated part of business processes" (workflow-dependence) replaced by a **material adverse impact** test for the basic regime. Annex flowchart and the "integrated use" example list (incl. the IT-helpdesk chatbot) deleted. | E/C | §2.2–2.4 | D-1.5, D-1.6, Annex ¶1–4 | Resp §3.6–3.8 |
| 3 | Basic policies: "annual review" → "periodic and trigger-based review"; "human review and validation of **all** AI outputs" → "effective human oversight (e.g., circumstances when mandatory human review ... is required)"; "guidelines" → "policies"; staff "education" and "regular compliance checks" retained; **new** requirement to review that §2.3 still holds. | E (review freq., human review) / T (§2.5(f)) | §2.5 | Annex ¶5 | Resp §3.15–3.16 |
| 4 | **Dedicated cross-functional AI committee removed.** FIs may use a centralised function or existing functions, provided management is consistent and coordinated. | R→E | §3.3 | D-2.4, D-fn12 | Resp §5.3 |
| 5 | **Group-basis application** added for locally incorporated FIs under consolidated supervision or owning CII. | N/T | §1.2 | — | Resp §2.3 |
| 6 | **Local senior management accountability** paragraph added (visibility, escalation, ability to demonstrate oversight to MAS even under group frameworks). | N/T | §3.6 | — | Resp §4.4 |
| 7 | AI identification must **minimally cover embedded AI in services from material third-party providers**; "robust systems" softened to "tools and systems as appropriate". | T (scope) / E (tooling) | §4.2, fn21 | D-3.2 | Resp §6.6, §6.10 |
| 8 | **Residual risk from unidentified AI** (shadow AI, embedded AI) must stay within appetite, with mitigations (policy + DLP/network monitoring). | N/T | §4.4, fn22 | — | Resp §6.7 |
| 9 | Inventory "accurate and up-to-date" → "accurate ... **to the extent possible or practicable**" with an FI-chosen update frequency; granularity made explicit; "validation status" → "model review status"; fn24 lets attribute sets differ if documented. | E/C | §4.5, §4.7, fn24 | D-3.4, D-3.5 | Resp §6.8, §6.16, §6.18 |
| 10 | **Agent inventory attributes** (identifiers, tools/systems accessible, components, guardrails) added as an example. | N | fn25 | — | Resp §6.15 |
| 11 | Materiality anchored on the **use case** (not system/model); dependencies between systems to be considered. | C/T | §4.10, fn26 | D-3.8 | Resp §7.5–7.6 |
| 12 | Complexity now includes **explainability** and **third-party visibility**; Reliance drops "availability of alternatives" and adds "level of reliance on AI (including third-party AI)". | C | §4.12(b)(c) | D-3.10(b)(c) | Resp §7.7, §7.13 |
| 13 | "Attestation processes" dropped from control-function duties for identification, inventory and materiality; replaced by outcome language and explicit permission for business units to execute with control-function oversight. | E | §4.3, §4.9, §4.13 | D-3.3, D-3.7, D-3.11 | Resp §8.5, §8.8 |
| 14 | Draft D-4.2 (define each use case, assign roles, assess, inventory, update through lifecycle) **removed** as a separate paragraph; its content is covered by §4.10–4.11 and §5.1. | R/C | — | D-4.2 | — |
| 15 | Data representativeness: "the **full** range of real-world conditions" → "**a** range". Privacy wording narrowed to consent for sensitive personal data used in training or processing. | E | §5.4(b)(f) | D-4.5(b)(f) | Resp §10.7 |
| 16 | Transparency: audience-needs sentence and fn34 (non-technical customer disclosures; IMDA chatbot guidance) added; "more exacting standards for explainability" → "higher level of transparency and explainability". | C/E | §5.6, fn34 | D-4.7 | Resp §10.12–10.15 |
| 17 | Fairness: FEAT named as a reference for defining "fair" outcomes. | C | §5.7, fn35 | D-4.8 | Resp §10.18 |
| 18 | Human oversight design must include **escalation mechanisms when predefined conditions are met** (decision deferral); documentation item expanded to **logs and records across development, deployment, operation, monitoring and incidents**. | T | §5.9(c)(d) | D-4.10(c)(d) | Resp §10.45, §10.50 |
| 19 | Third-party AI: FI's **primary accountability** stated; **limit / suspend / replace** when residual risk exceeds appetite; **certifications or external assessments by independent parties (not self-attestations)** accepted to address transparency gaps; contractual visibility over AI introduction **and updates**; development controls apply when fine-tuning (fn38); documentation of suitability testing required. | T | §5.10–5.11 | D-4.11 | Resp §9.3–9.5, §9.9, §9.14 |
| 20 | Third-party AI: the draft's standalone **Fairness** consideration removed (folded into transparency list); **Change Management** became an explicit consideration (ability to receive update notifications), replacing the draft's absolute duty to "establish processes to receive notifications of updates". | E/C | §5.11(a)(d) | D-4.11(b), D-4.11 chapeau | Resp §9.13–9.15 |
| 21 | Selection: "require developers to justify and document" → "document their considerations ... commensurate with risk materiality"; "supported by theory, research or accepted industry practice where possible" → "may draw reference from research or accepted industry practice". | E | §5.12 | D-4.12 | Resp §10.24–10.25 |
| 22 | Evaluation of GenAI/agents must cover key failure modes **and the effectiveness of associated guardrails**. | T | §5.15, fn46 | D-4.15, D-fn27 | Resp §12.7 |
| 23 | Pilots/phased rollouts explicitly allowed as a way to gather representative data (fn45). | C/E | fn45 | — | Resp §10.31 |
| 24 | Technology & cyber controls made explicitly **proportionate** to materiality; "robust privileged account access management" added; CSA Securing-AI guidance referenced (fn3). | C | §5.16, fn3 | D-4.16 | Resp §10.36, §10.38 |
| 25 | Reproducibility: documentation rigour commensurate with materiality; replication target changed from "the AI system or model **and its results**" to "its **evaluation and testing process**" (non-deterministic GenAI). | E | §5.17 | D-4.17 | Resp §10.43–10.44 |
| 26 | Independent validation scope: "areas **relevant to the AI use case**, such as" (not a checklist). | C/E | §5.19 | D-4.19 | Resp §10.60 |
| 27 | Monitoring: incident item renamed "AI Incident and Issue Management"; **AI incident defined** (fn20); **enhanced GenAI/agent logging** (prompts, responses, model versions, reasoning) added as a consideration. | N/C | §5.23(b)(d), fn20 | D-4.23 | Resp §10.45, §10.69 |
| 28 | Draft duty to "periodically review **aggregate risks across all AI** use cases" **removed**; re-validation "where necessary", frequency informed by materiality; independent re-validation retained for high risk. | R/E | §5.24 | D-4.24 | Resp §10.68 |
| 29 | Change management: fixed significant/minor split (retraining = minor) replaced by an FI-defined **change assessment framework**; **compensating controls** (enhanced monitoring) where significant changes occur without prior review (vendor updates); "human-in-the-loop" → "appropriate human oversight". | C/T | §5.25(a)(b), fn49 | D-4.25(a)(b) | Resp §10.73–10.74 |
| 30 | Capability: competence and conduct extended to personnel **using** AI, not only developing/deploying. | T | §6.1 | D-5.1 | Resp §11.4 |
| 31 | Board: approve **and regularly review** governance approach and **strategic direction for AI use**; "AI risks, where material" → "risks from AI use" (qualifier removed); fn18 risk-appetite examples; fn17 group committees; fn19 three lines of defence. | T/C | §3.4, fn17–19 | D-2.5 | Resp §4.3, §4.10, §4.12 |
| 32 | Senior management: explicit duty to institute lifecycle controls (§3.5(c)) and to establish control functions for identification/inventory/materiality (§3.5(d)). | T/C | §3.5 | D-2.6 | Resp §4.7 |
| 33 | Definition of AI restated (§1.3) with fn6 giving **in-scope and out-of-scope examples** (Monte Carlo, expert systems, RPA excluded). | C | §1.3, fn6 | D-1.2(d), D-fn5 | Resp §2.7–2.8 |
| 34 | Third-party AI definition rewritten to cover services or tools **incorporating or using AI** that the FI procures, subscribes to, accesses or relies on. | C/T | fn10 | D-fn10 | Resp §2.10–2.11 |
| 35 | Risks section: **shadow AI** and **automation bias** added to human-factor risks; agent risk paragraph now says "unauthorised or erroneous actions"; IMDA agentic framework referenced (fn11). | C | §1.10(f), §1.11, fn11 | D-1.9(f), D-1.10 | Resp §12.9 |
| 36 | §1.2 now says the Guidelines "complement existing legislation and guidelines" (outsourcing/TPRM, TRM) — not an exhaustive list. | C | §1.2 | D-1.1 | Resp §9.18 |

## 2. Paragraph concordance

| Final | Draft | Note |
|---|---|---|
| 1.1 | 1.1 | |
| 1.2 | 1.1 (part), fn3 | group basis new |
| 1.3 | 1.2(d) | definition restated |
| 1.4 | 1.2(a)–(c) | |
| 1.5 | 1.3 | |
| 1.6 | 1.4 | |
| 1.7 | 1.7 | |
| 1.8 | — (CP §4.7) | new |
| 1.9 | 1.8 | |
| 1.10 | 1.9 | (f) expanded |
| 1.11 | 1.10 | |
| 1.12 | 1.11 | |
| 2.1 | — | new |
| 2.2 | 1.5, 1.6 | rewritten |
| 2.3 | Annex ¶2 | test replaced |
| 2.4 | Annex ¶3 | examples re-cut; (f) internal chatbot now *basic* |
| 2.5 | 1.5, Annex ¶5 | expanded |
| 3.1 | 2.1 | |
| 3.2 | 2.2, 2.3 | consolidated |
| 3.3 | 2.4 | committee removed |
| 3.4 | 2.5 | |
| 3.5 | 2.6 | (c),(d) new |
| 3.6 | — | new |
| 4.1 | 3.1 | |
| 4.2 | 3.2 | |
| 4.3 | 3.3 | |
| 4.4 | — | new |
| 4.5 | 3.4 (part) | |
| 4.6 | 3.4 (part) | |
| 4.7 | 3.5 | |
| 4.8 | 3.6 | fn25 new |
| 4.9 | 3.7 | |
| 4.10 | 3.8 | |
| 4.11 | 3.9 | |
| 4.12 | 3.10 | |
| 4.13 | 3.11 | |
| 5.1 | 4.1 | |
| — | 4.2 | removed |
| 5.2 | 4.3 | |
| 5.3 | 4.4 | |
| 5.4 | 4.5 | |
| 5.5 | 4.6 | |
| 5.6 | 4.7 | |
| 5.7 | 4.8 | |
| 5.8 | 4.9 | |
| 5.9 | 4.10 | |
| 5.10 | 4.11 (chapeau) | |
| 5.11 | 4.11(a)–(h) | restructured |
| 5.12 | 4.12 | |
| 5.13 | 4.13 | |
| 5.14 | 4.14 | |
| 5.15 | 4.15 | guardrail effectiveness added |
| 5.16 | 4.16 | |
| 5.17 | 4.17 | |
| 5.18 | 4.18 | |
| 5.19 | 4.19 | |
| 5.20 | 4.20 | |
| 5.21 | 4.21 | |
| 5.22 | 4.22 | |
| 5.23 | 4.23 | |
| 5.24 | 4.24 | aggregate review removed |
| 5.25 | 4.25 | |
| 5.26 | 4.26 | |
| 6.1 | 5.1 | "and using" added |
| 6.2 | 5.2 | |
| 6.3 | 5.3 | |

## 3. Net assessment

- **Net direction: eased on process, tightened on substance for newer AI.** The final text removes
  most prescriptive organisational mechanics (dedicated committee, attestation processes, annual
  reviews, "all outputs reviewed", aggregate portfolio reviews, "full range" of data conditions) and
  replaces them with outcome language plus proportionality. At the same time it adds concrete
  obligations that did not exist in the draft: embedded-AI identification for material providers,
  shadow-AI residual-risk management, agent inventory attributes, guardrail-effectiveness testing,
  GenAI/agent logging, local senior management accountability, vendor limit/suspend/replace, and
  rejection of vendor self-attestations.
- **For LLM and agentic systems specifically**, the binding deltas are §4.4/fn22, fn25, §5.9(c)(d),
  §5.11(a)(d), §5.15/fn46, §5.23(a)(d) and §5.25(a). These are the clauses the toolkit's `genai`
  and `agent` tags key on.
- **Nothing in the Response to Feedback prescribes metrics, thresholds, or a formula** for combining
  Impact / Complexity / Reliance (Resp §7.19, §10.28–10.29, §10.66). Every quantitative default in
  this toolkit is therefore the authors' proposal, not MAS'.
