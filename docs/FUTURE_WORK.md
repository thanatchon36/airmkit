# Future work

Ordered by how much it would improve the toolkit's usefulness per unit of effort.

## Catalogue and interpretation
- Re-run clause extraction when MAS updates the Guidelines (Response §12.9 signals further
  agentic-AI guidance and a separate consultation). The catalogue carries a source SHA-256 so drift
  is detectable.
- Incorporate the Project MindForge industry AI Risk Management Handbook (companion guide to the
  Guidelines) once public; the consultation paper footnote 5 promised it for January 2026.
- Add the MAS Consultation Paper on Proposed Guidelines on Third-Party Risk Management (6 Mar 2026,
  referenced in Response footnote 3) once finalised, since it will supersede the Outsourcing
  Guidelines that §5.10 fn39 relies on.

## Crosswalks (the clearest contribution others can make)
- HKMA (GenAI consumer protection circular, AI in AML), BNM Malaysia, Bank of Thailand, APRA
  CPS 230/234, RBI, and the EU AI Act GPAI chapter.
- ISO/IEC 42005 (AI impact assessment) and 42006 (certification body requirements) when published.
- SOC 2 and ISO 27001 mappings for the §5.16 security controls, which most FIs already evidence.

## Evaluation adapters
- Native readers for `inspect-ai` `.eval` log bundles (currently JSON log export only), promptfoo
  share URLs, and OpenTelemetry GenAI spans for the §5.23(a) agent-trace monitoring.
- Agent tool-scope audit against MCP server manifests, so "observed tools ⊆ approved tools" can be
  checked from a trace rather than from a declaration.
- A proper statistical design for RQ3: multiple runs per probe, several model families and sizes,
  and power analysis for the tier thresholds.

## Library
- `airm diff` on two register versions producing a change-significance classification per §5.25(a).
- Signed evidence records (Sigstore / minisign) instead of hash-chaining alone.
- A read-only web view of the audit pack for reviewers who will not install Python.
- Localisation of the report templates (the audit pack is English only).

## Research
- Measure, rather than estimate, the person-hours in RQ5 with a small user study on the synthetic
  portfolio.
- Test whether two independent annotators agree on the RQ1 automatability classes.
- Compare the default materiality rubric against the tiers real institutions report in the MAS
  Information Paper 2024, to see whether the rubric reproduces observed practice.
