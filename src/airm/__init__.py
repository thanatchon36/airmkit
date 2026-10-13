"""airmkit: operationalise the MAS Guidelines on AI Risk Management for LLM and agentic systems.

This package turns the MAS Guidelines on Artificial Intelligence Risk Management (issued
7 October 2026) into machine-readable artefacts: a clause catalogue, an AI inventory schema,
a risk-materiality rubric, a control catalogue with automated checks, evidence records and
audit-ready reports.

**This is an independent open-source project. It is not affiliated with, endorsed by or reviewed
by the Monetary Authority of Singapore. It is not legal, regulatory or compliance advice, and it
is not a substitute for reading the Guidelines. See DISCLAIMER.md.**

Every public function names the MAS paragraph(s) it serves, cited as ``MAS-AIRM §x.y``, where the
paragraph numbers refer to the final Guidelines of 7 October 2026. Summaries in the catalogue are
the authors' paraphrase, never the regulatory text.

Modules
-------
``airm.catalog``
    The clause index: paragraphs, footnotes, tags, effective dates (MAS-AIRM §1.8).
``airm.inventory``
    AI inventory models and register (MAS-AIRM §4.5-§4.9, footnote 25).
``airm.materiality``
    Impact / Complexity / Reliance rubric scoring (MAS-AIRM §4.10-§4.13).
``airm.controls``
    Control catalogue mapped to Section 5 lifecycle controls, with checks.
``airm.evals``
    Adapters mapping existing eval-tool output to controls (MAS-AIRM §5.14-§5.15).
``airm.monitor``
    Hash-chained evidence and audit trail (MAS-AIRM §5.17, §5.23).
``airm.thirdparty``
    Third-party AI assessment records (MAS-AIRM §5.10-§5.11).
``airm.crosswalk``
    Mappings to ISO/IEC 42001, NIST AI RMF, EU AI Act, FEAT.
``airm.scan``
    Shadow-AI discovery over repositories and configs (MAS-AIRM §4.2, §4.4).
``airm.report``
    Audit-pack generation (inventory register, materiality report, applicability statement, gaps).
"""

from __future__ import annotations

__all__ = [
    "DISCLAIMER",
    "__version__",
]

__version__ = "0.1.0"

DISCLAIMER = (
    "airmkit is an independent open-source project, not affiliated with or endorsed by the "
    "Monetary Authority of Singapore. It is not legal, regulatory or compliance advice and is "
    "not a substitute for reading the Guidelines on Artificial Intelligence Risk Management "
    "(7 October 2026). Interpretations and all thresholds are the authors'."
)
