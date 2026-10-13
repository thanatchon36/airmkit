"""Shadow-AI and embedded-AI discovery over repositories and configuration.

Serves MAS-AIRM §4.2 (consistent identification of AI use across all business and functional
areas, minimally covering AI in services from material third-party providers) and §4.4 with
footnote 22 (identify the risks from constraints on identification and mitigate them, including
through technical controls).

**What this is.** A text scanner that flags signals of AI use in code and configuration: LLM SDK
imports, model API endpoints, MCP server configurations, agent frameworks and vendor AI SaaS
references. Its output is a list of *candidate* inventory entries for human triage.

**What this is not.** Assurance of completeness. Response to Feedback §6.7 accepts that complete
identification may not be practically possible; §6.10-§6.11 leaves the choice of discovery tooling
to the FI. A clean scan means this scanner found nothing, which is not the same as there being
nothing. The control catalogue therefore classes the identification control as ``doc`` and treats
scan output as partial evidence only.

**Safety.** Scanned files are untrusted data. Nothing found is imported, executed, evaluated or
resolved; files are read as text with errors replaced, size-capped, and matched against regular
expressions. Secrets are never echoed: matched lines are redacted before being recorded.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from airm.catalog import cite
from airm.inventory import AutonomyLevel, LifecycleStatus, UseCase

__all__ = [
    "DEFAULT_EXCLUDES",
    "Finding",
    "ScanReport",
    "Signal",
    "SignalKind",
    "scan_path",
    "to_use_cases",
]

MAX_FILE_BYTES = 2_000_000
"""Files larger than this are skipped: they are data or binaries, not configuration."""

MAX_LINE_CHARS = 400
"""Matched lines longer than this are truncated before recording."""

DEFAULT_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        "site-packages",
        ".tox",
        ".next",
        "target",
        "vendor",
        ".terraform",
        "htmlcov",
    }
)
"""Directory names skipped by default: dependencies and build output, not the FI's own AI use."""

SCANNED_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".ipynb",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".kt",
        ".scala",
        ".go",
        ".rb",
        ".rs",
        ".cs",
        ".php",
        ".r",
        ".sql",
        ".sh",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".properties",
        ".tf",
        ".tfvars",
        ".md",
        ".txt",
        ".dockerfile",
        ".gradle",
        ".xml",
    }
)

_EXTRA_FILENAMES: frozenset[str] = frozenset(
    {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "Pipfile",
        "poetry.lock",
        "environment.yml",
        ".env",
        ".mcp.json",
        "mcp.json",
        "claude_desktop_config.json",
    }
)

_SECRET_PATTERN = re.compile(
    r"""(?ix)
    (sk-[A-Za-z0-9_\-]{12,}
    |AIza[0-9A-Za-z_\-]{20,}
    |xox[abprs]-[A-Za-z0-9\-]{10,}
    |gh[pousr]_[A-Za-z0-9]{16,}
    |AKIA[0-9A-Z]{12,}
    |ASIA[0-9A-Z]{12,}
    |hf_[A-Za-z0-9]{16,}
    |-{5}BEGIN[A-Z\s]*PRIVATE\s+KEY-{5}
    |ey[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}
    |(?:api[_-]?key|apikey|token|secret|password|passwd|bearer|credential)\s*[:=]\s*["']?[A-Za-z0-9_\-/+.]{12,})
    """
)


class SignalKind(StrEnum):
    """What kind of AI usage a signal indicates.

    The kinds map onto the identification scope the Guidelines set: ``llm_sdk``, ``model_endpoint``
    and ``agent_framework`` are AI the FI builds with; ``mcp_config`` and ``tool_integration`` are
    the tool access that §1.11 and §4.8 footnote 25 care about; ``vendor_ai_saas`` is the embedded
    AI of §4.2 footnote 21; ``public_ai_tool`` is the shadow-AI exposure of §4.4 footnote 22.
    """

    LLM_SDK = "llm_sdk"
    MODEL_ENDPOINT = "model_endpoint"
    LOCAL_MODEL = "local_model"
    AGENT_FRAMEWORK = "agent_framework"
    MCP_CONFIG = "mcp_config"
    TOOL_INTEGRATION = "tool_integration"
    ML_FRAMEWORK = "ml_framework"
    VENDOR_AI_SAAS = "vendor_ai_saas"
    PUBLIC_AI_TOOL = "public_ai_tool"
    EVAL_TOOLING = "eval_tooling"
    GUARDRAIL = "guardrail"

    @property
    def citation(self) -> str:
        """Return the MAS-AIRM paragraph this kind is evidence for."""
        return _KIND_CITATIONS[self]

    @property
    def suggests_agent(self) -> bool:
        """Whether this kind suggests an agentic use case (MAS-AIRM §1.11, §4.8 fn25)."""
        return self in (
            SignalKind.AGENT_FRAMEWORK,
            SignalKind.MCP_CONFIG,
            SignalKind.TOOL_INTEGRATION,
        )


_KIND_CITATIONS: dict[SignalKind, str] = {
    SignalKind.LLM_SDK: cite("4.2"),
    SignalKind.MODEL_ENDPOINT: cite("4.2"),
    SignalKind.LOCAL_MODEL: cite("4.2"),
    SignalKind.AGENT_FRAMEWORK: cite("4.8", footnote=25),
    SignalKind.MCP_CONFIG: cite("4.8", footnote=25),
    SignalKind.TOOL_INTEGRATION: cite("4.8", footnote=25),
    SignalKind.ML_FRAMEWORK: cite("1.3", footnote=6),
    SignalKind.VENDOR_AI_SAAS: cite("4.2", footnote=21),
    SignalKind.PUBLIC_AI_TOOL: cite("4.4", footnote=22),
    SignalKind.EVAL_TOOLING: cite("5.14"),
    SignalKind.GUARDRAIL: cite("5.15"),
}


class Signal(BaseModel):
    """A detection rule: a name, a kind, a regular expression and a confidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: SignalKind
    label: str
    pattern: str
    confidence: str = Field(default="medium", description="'high', 'medium' or 'low'.")
    note: str = ""

    def compiled(self) -> re.Pattern[str]:
        """Return the compiled, case-insensitive pattern."""
        return re.compile(self.pattern, re.IGNORECASE)


# Detection rules. Patterns match imports, endpoints and configuration keys rather than arbitrary
# mentions, to keep the false-positive rate low enough for human triage to be worth doing.
SIGNALS: tuple[Signal, ...] = (
    # -- LLM SDKs and clients
    Signal(
        id="SDK-ANTHROPIC",
        kind=SignalKind.LLM_SDK,
        label="Anthropic SDK",
        confidence="high",
        pattern=(
            r"\b(from|import)\s+anthropic\b|@anthropic-ai/|\bAnthropic\("
            r"|anthropic\.(Client|Anthropic)\b"
        ),
    ),
    Signal(
        id="SDK-OPENAI",
        kind=SignalKind.LLM_SDK,
        label="OpenAI SDK",
        confidence="high",
        pattern=r"\b(from|import)\s+openai\b|\bfrom\s+['\"]openai['\"]|\bOpenAI\(|AzureOpenAI\(",
    ),
    Signal(
        id="SDK-GOOGLE-GENAI",
        kind=SignalKind.LLM_SDK,
        label="Google GenAI SDK",
        confidence="high",
        pattern=r"google[._-]genai|google\.generativeai|@google/generative-ai|vertexai\b",
    ),
    Signal(
        id="SDK-BEDROCK",
        kind=SignalKind.LLM_SDK,
        label="AWS Bedrock",
        confidence="high",
        pattern=r"bedrock[-_]?runtime|\bbedrock\b.*invoke_model|BedrockRuntime",
    ),
    Signal(
        id="SDK-COHERE",
        kind=SignalKind.LLM_SDK,
        label="Cohere SDK",
        confidence="high",
        pattern=r"\b(from|import)\s+cohere\b|cohere-ai",
    ),
    Signal(
        id="SDK-MISTRAL",
        kind=SignalKind.LLM_SDK,
        label="Mistral SDK",
        confidence="high",
        pattern=r"mistralai\b|@mistralai/",
    ),
    Signal(
        id="SDK-HUGGINGFACE",
        kind=SignalKind.LLM_SDK,
        label="Hugging Face",
        confidence="medium",
        pattern=r"\b(from|import)\s+transformers\b|huggingface_hub|@huggingface/|AutoModelFor",
    ),
    Signal(
        id="SDK-LITELLM",
        kind=SignalKind.LLM_SDK,
        label="LiteLLM proxy",
        confidence="high",
        pattern=r"\b(from|import)\s+litellm\b|litellm\.(completion|acompletion)",
    ),
    # -- model endpoints
    Signal(
        id="EP-ANTHROPIC",
        kind=SignalKind.MODEL_ENDPOINT,
        label="Anthropic API endpoint",
        confidence="high",
        pattern=r"api\.anthropic\.com",
    ),
    Signal(
        id="EP-OPENAI",
        kind=SignalKind.MODEL_ENDPOINT,
        label="OpenAI API endpoint",
        confidence="high",
        pattern=r"api\.openai\.com|openai\.azure\.com",
    ),
    Signal(
        id="EP-GOOGLE",
        kind=SignalKind.MODEL_ENDPOINT,
        label="Google AI endpoint",
        confidence="high",
        pattern=r"generativelanguage\.googleapis\.com|aiplatform\.googleapis\.com",
    ),
    Signal(
        id="EP-AWS",
        kind=SignalKind.MODEL_ENDPOINT,
        label="AWS Bedrock endpoint",
        confidence="high",
        pattern=r"bedrock(-runtime)?\.[a-z0-9-]+\.amazonaws\.com",
    ),
    Signal(
        id="EP-OTHER",
        kind=SignalKind.MODEL_ENDPOINT,
        label="Other hosted model endpoint",
        confidence="medium",
        pattern=r"api\.(groq|together|mistral|deepseek|perplexity|fireworks|replicate)\.(com|ai|xyz)",
    ),
    Signal(
        id="MODEL-ID",
        kind=SignalKind.MODEL_ENDPOINT,
        label="Foundation model identifier",
        confidence="medium",
        pattern=r"\b(claude-[a-z0-9.\-]+|gpt-[0-9][a-z0-9.\-]*|gemini-[a-z0-9.\-]+|llama-?[0-9][a-z0-9.\-]*|mistral-[a-z0-9.\-]+|qwen[0-9.]*)\b",
    ),
    # -- local models
    Signal(
        id="LOCAL-OLLAMA",
        kind=SignalKind.LOCAL_MODEL,
        label="Ollama",
        confidence="high",
        pattern=r"\b(from|import)\s+ollama\b|localhost:11434|ollama\.(chat|generate|pull)",
    ),
    Signal(
        id="LOCAL-LLAMACPP",
        kind=SignalKind.LOCAL_MODEL,
        label="llama.cpp or vLLM",
        confidence="high",
        pattern=r"llama[_-]?cpp|\bvllm\b|text-generation-webui|localai\b",
    ),
    Signal(
        id="LOCAL-WEIGHTS",
        kind=SignalKind.LOCAL_MODEL,
        label="Local model weights",
        confidence="low",
        pattern=r"\.(gguf|safetensors|onnx|pt|pth|ggml)\b",
    ),
    # -- agent frameworks
    Signal(
        id="AGENT-LANGCHAIN",
        kind=SignalKind.AGENT_FRAMEWORK,
        label="LangChain or LangGraph",
        confidence="high",
        pattern=r"\b(from|import)\s+lang(chain|graph)\b|langchain[_.\-]|langgraph[_.\-]|@langchain/",
    ),
    Signal(
        id="AGENT-LLAMAINDEX",
        kind=SignalKind.AGENT_FRAMEWORK,
        label="LlamaIndex",
        confidence="high",
        pattern=r"llama[_-]?index\b|\bfrom\s+llama_index",
    ),
    Signal(
        id="AGENT-CREW",
        kind=SignalKind.AGENT_FRAMEWORK,
        label="CrewAI or AutoGen",
        confidence="high",
        pattern=r"\bcrewai\b|\bautogen\b|\bag2\b|pyautogen",
    ),
    Signal(
        id="AGENT-SDK",
        kind=SignalKind.AGENT_FRAMEWORK,
        label="Agent SDK",
        confidence="high",
        pattern=r"agents?[_-]sdk|claude[_-]agent[_-]sdk|openai[_-]agents|smolagents|pydantic[_-]ai|\bhaystack\b",
    ),
    Signal(
        id="AGENT-SEMANTIC",
        kind=SignalKind.AGENT_FRAMEWORK,
        label="Semantic Kernel",
        confidence="high",
        pattern=r"semantic[_-]kernel|Microsoft\.SemanticKernel",
    ),
    Signal(
        id="AGENT-LOOP",
        kind=SignalKind.AGENT_FRAMEWORK,
        label="Agent loop construct",
        confidence="low",
        pattern=r"\b(AgentExecutor|create_react_agent|ToolNode|tool_calls|function_call(ing)?)\b",
    ),
    # -- MCP and tool integration
    Signal(
        id="MCP-CONFIG",
        kind=SignalKind.MCP_CONFIG,
        label="MCP server configuration",
        confidence="high",
        pattern=r"mcpServers|model[_-]context[_-]protocol|\bmcp\.json\b|@modelcontextprotocol/",
    ),
    Signal(
        id="MCP-SDK",
        kind=SignalKind.MCP_CONFIG,
        label="MCP SDK",
        confidence="high",
        pattern=r"\b(from|import)\s+mcp\b|mcp\.server|FastMCP",
    ),
    Signal(
        id="TOOL-DEF",
        kind=SignalKind.TOOL_INTEGRATION,
        label="Tool or function definition",
        confidence="low",
        pattern=r"@tool\b|StructuredTool|tool_choice|\"tools\"\s*:\s*\[|parallel_tool_calls",
    ),
    # -- classical ML
    Signal(
        id="ML-SKLEARN",
        kind=SignalKind.ML_FRAMEWORK,
        label="scikit-learn",
        confidence="high",
        pattern=r"\b(from|import)\s+sklearn\b|scikit-learn",
    ),
    Signal(
        id="ML-BOOST",
        kind=SignalKind.ML_FRAMEWORK,
        label="Gradient boosting library",
        confidence="high",
        pattern=r"\b(xgboost|lightgbm|catboost)\b",
    ),
    Signal(
        id="ML-DL",
        kind=SignalKind.ML_FRAMEWORK,
        label="Deep learning framework",
        confidence="high",
        pattern=r"\b(from|import)\s+(torch|tensorflow|keras|jax|flax)\b|pytorch[_-]lightning",
    ),
    Signal(
        id="ML-STATS",
        kind=SignalKind.ML_FRAMEWORK,
        label="Statistical modelling",
        confidence="low",
        pattern=r"\b(from|import)\s+statsmodels\b|\bglm\(|LogisticRegression",
    ),
    # -- vendor AI SaaS and embedded AI
    Signal(
        id="SAAS-COPILOT",
        kind=SignalKind.VENDOR_AI_SAAS,
        label="Microsoft Copilot",
        confidence="medium",
        pattern=r"\bm365[_-]?copilot\b|microsoft[_-]?copilot|graph\.microsoft\.com/.*copilot",
    ),
    Signal(
        id="SAAS-CRM-AI",
        kind=SignalKind.VENDOR_AI_SAAS,
        label="Vendor AI feature in SaaS",
        confidence="medium",
        pattern=r"\b(einstein[_-]?(gpt|ai)|salesforce[_-]?ai|servicenow[_-]?ai|sap[_-]?ai[_-]?core|workday[_-]?ai|zendesk[_-]?ai|intercom[_-]?fin)\b",
    ),
    Signal(
        id="SAAS-DOC-AI",
        kind=SignalKind.VENDOR_AI_SAAS,
        label="Document or speech AI service",
        confidence="medium",
        pattern=r"\b(textract|rekognition|comprehend|document[_-]?ai|form[_-]?recognizer|cognitiveservices|transcribe)\b",
    ),
    Signal(
        id="SAAS-VECTOR",
        kind=SignalKind.VENDOR_AI_SAAS,
        label="Vector database or RAG service",
        confidence="medium",
        pattern=r"\b(pinecone|weaviate|qdrant|chromadb|milvus|pgvector|opensearch.*knn)\b",
    ),
    # -- public AI tools (shadow AI exposure)
    Signal(
        id="PUBLIC-CHAT",
        kind=SignalKind.PUBLIC_AI_TOOL,
        label="Public AI chat tool reference",
        confidence="low",
        pattern=r"\b(chatgpt\.com|chat\.openai\.com|claude\.ai|gemini\.google\.com|copilot\.microsoft\.com|perplexity\.ai)\b",
        note=(
            "A reference in code or config suggests staff use of a public tool "
            "(MAS-AIRM §4.4 fn22)."
        ),
    ),
    # -- eval and guardrail tooling (positive signals: controls may already exist)
    Signal(
        id="EVAL-TOOLING",
        kind=SignalKind.EVAL_TOOLING,
        label="LLM evaluation tooling",
        confidence="high",
        pattern=(
            r"\b(inspect_ai|inspect-ai|promptfoo|deepeval|ragas|trulens|langfuse"
            r"|phoenix[_-]?arize|braintrust)\b"
        ),
    ),
    Signal(
        id="GUARDRAIL-TOOLING",
        kind=SignalKind.GUARDRAIL,
        label="Guardrail tooling",
        confidence="high",
        pattern=r"\b(guardrails[_-]?ai|nemoguardrails|llama[_-]?guard|presidio|garak|rebuff|lakera)\b",
    ),
)


class Finding(BaseModel):
    """One match of one signal in one file."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str
    kind: SignalKind
    label: str
    confidence: str
    path: str
    line: int
    excerpt: str = Field(description="The matched line, truncated and secret-redacted.")
    citation: str

    @property
    def location(self) -> str:
        """Return a clickable ``path:line`` reference."""
        return f"{self.path}:{self.line}"


class ScanReport(BaseModel):
    """The result of a scan.

    The report is explicitly *candidates for triage*, not an inventory. ``caveat`` is carried in
    the serialised output so that the limitation travels with the data into whatever consumes it.
    """

    model_config = ConfigDict(extra="forbid")

    root: str
    scanned_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(tz=dt.UTC))
    files_scanned: int = 0
    files_skipped: int = 0
    findings: list[Finding] = Field(default_factory=list)
    citations: list[str] = Field(
        default_factory=lambda: [cite("4.2"), cite("4.4"), cite("4.4", footnote=22)]
    )
    caveat: str = Field(
        default=(
            "Candidate signals for human triage, not an inventory and not assurance of "
            "completeness. A clean scan means this scanner found nothing, not that there is "
            "nothing. MAS-AIRM §4.3 makes a designated control function the final arbiter of "
            "whether a given use constitutes AI use."
        )
    )

    @property
    def kinds(self) -> dict[str, int]:
        """Count of findings per signal kind."""
        out: dict[str, int] = {}
        for finding in self.findings:
            out[finding.kind.value] = out.get(finding.kind.value, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    @property
    def by_directory(self) -> dict[str, list[Finding]]:
        """Group findings by the directory of the file, which is the triage unit."""
        out: dict[str, list[Finding]] = {}
        for finding in self.findings:
            out.setdefault(str(Path(finding.path).parent), []).append(finding)
        return dict(sorted(out.items()))

    @property
    def has_agent_signals(self) -> bool:
        """Whether any finding suggests agentic AI (MAS-AIRM §1.11, §4.8 fn25)."""
        return any(f.kind.suggests_agent for f in self.findings)

    @property
    def shadow_ai_findings(self) -> tuple[Finding, ...]:
        """Findings suggesting use of public AI tools (MAS-AIRM §4.4 fn22)."""
        return tuple(f for f in self.findings if f.kind is SignalKind.PUBLIC_AI_TOOL)

    @property
    def embedded_ai_findings(self) -> tuple[Finding, ...]:
        """Findings suggesting AI embedded in third-party services (MAS-AIRM §4.2 fn21)."""
        return tuple(f for f in self.findings if f.kind is SignalKind.VENDOR_AI_SAAS)

    def summary_lines(self) -> list[str]:
        """Return human-readable summary lines for the CLI."""
        lines = [
            f"scanned {self.files_scanned} file(s), skipped {self.files_skipped}",
            f"{len(self.findings)} signal(s) across {len(self.by_directory)} directory group(s)",
        ]
        lines.extend(f"  {kind}: {count}" for kind, count in self.kinds.items())
        if self.shadow_ai_findings:
            lines.append(
                f"  public AI tool references: {len(self.shadow_ai_findings)} "
                f"({cite('4.4', footnote=22)})"
            )
        return lines


def _redact(line: str) -> str:
    """Remove anything that looks like a credential from a matched line.

    The scanner reads files that may contain secrets. A finding that echoed an API key would move
    the secret into a report and possibly into version control, so credentials are replaced before
    the line is recorded.
    """
    return _SECRET_PATTERN.sub("[REDACTED]", line.strip())[:MAX_LINE_CHARS]


def _should_scan(path: Path) -> bool:
    """Whether a file is a candidate for scanning."""
    if path.name in _EXTRA_FILENAMES:
        return True
    if path.name.startswith(".env"):
        return True
    return path.suffix.lower() in SCANNED_SUFFIXES


def _iter_files(root: Path, excludes: frozenset[str]) -> Iterator[Path]:
    """Walk a tree, skipping excluded directories and symlinks.

    Symlinks are skipped so that a scanned repository cannot redirect the scanner outside the
    tree it was pointed at.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in excludes:
                    stack.append(entry)
            elif entry.is_file():
                yield entry


def scan_path(
    root: str | Path,
    *,
    excludes: Iterable[str] | None = None,
    signals: Iterable[Signal] | None = None,
    min_confidence: str = "low",
) -> ScanReport:
    r"""Scan a directory tree for signals of AI use.

    Serves MAS-AIRM §4.2 and §4.4: it gives a designated control function somewhere to start when
    identifying AI use, including embedded AI (§4.2 fn21) and shadow AI (§4.4 fn22).

    Scanned content is treated as untrusted data throughout: files are read as text, never
    imported or executed; symlinks are skipped; matched lines are secret-redacted.

    Args:
        root: Directory (or single file) to scan.
        excludes: Directory names to skip; defaults to :data:`DEFAULT_EXCLUDES`.
        signals: Detection rules; defaults to the built-in :data:`SIGNALS`.
        min_confidence: Drop findings below this confidence ('low', 'medium', 'high').

    Returns:
        A :class:`ScanReport` of candidate findings.

    Examples:
        >>> import tempfile, pathlib
        >>> with tempfile.TemporaryDirectory() as d:
        ...     _ = (pathlib.Path(d) / "app.py").write_text("import anthropic\\n")
        ...     report = scan_path(d)
        ...     report.kinds
        {'llm_sdk': 1}
    """
    target = Path(root)
    exclude_set = frozenset(excludes) if excludes is not None else DEFAULT_EXCLUDES
    rules = tuple(signals) if signals is not None else SIGNALS
    order = {"low": 0, "medium": 1, "high": 2}
    floor = order.get(min_confidence, 0)
    compiled = [(rule, rule.compiled()) for rule in rules if order[rule.confidence] >= floor]

    findings: list[Finding] = []
    scanned = 0
    skipped = 0

    candidates = [target] if target.is_file() else list(_iter_files(target, exclude_set))
    for path in sorted(candidates):
        if not _should_scan(path):
            skipped += 1
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                skipped += 1
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            skipped += 1
            continue
        scanned += 1
        try:
            display = str(path.relative_to(target)) if target.is_dir() else str(path)
        except ValueError:
            display = str(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if len(line) > 10_000:
                continue
            for rule, pattern in compiled:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            signal_id=rule.id,
                            kind=rule.kind,
                            label=rule.label,
                            confidence=rule.confidence,
                            path=display,
                            line=lineno,
                            excerpt=_redact(line),
                            citation=rule.kind.citation,
                        )
                    )
    return ScanReport(
        root=str(target), files_scanned=scanned, files_skipped=skipped, findings=findings
    )


def to_use_cases(report: ScanReport, *, group_by: str = "directory") -> list[UseCase]:
    """Turn a scan report into candidate inventory entries for human triage.

    Serves MAS-AIRM §4.5 and §4.7: the candidates are shaped like inventory entries so that a
    reviewer can promote one into the register by filling in the attributes the scanner cannot
    know (purpose, approved scope, owner, materiality).

    Every candidate is created as ``lifecycle_status: proposed`` with a note recording the signals
    it came from, because §4.3 makes the designated control function, not a scanner, the final
    arbiter of whether something is AI use.

    Args:
        report: The scan report.
        group_by: ``"directory"`` (one candidate per directory) or ``"file"``.

    Returns:
        Candidate :class:`~airm.inventory.UseCase` entries, never written to a register
        automatically.
    """
    groups: dict[str, list[Finding]] = {}
    for finding in report.findings:
        key = str(Path(finding.path).parent) if group_by == "directory" else finding.path
        groups.setdefault(key, []).append(finding)

    candidates: list[UseCase] = []
    for index, (key, found) in enumerate(sorted(groups.items()), start=1):
        kinds = {f.kind for f in found}
        slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-") or "root"
        agentic = any(k.suggests_agent for k in kinds)
        labels = sorted({f.label for f in found})
        tags = sorted({k.value.replace("_", "-") for k in kinds})
        if any(k in kinds for k in (SignalKind.LLM_SDK, SignalKind.LOCAL_MODEL)):
            tags.append("genai")
        if agentic:
            tags.append("agent")
        candidates.append(
            UseCase(
                id=f"candidate-{index:02d}-{slug}"[:64].rstrip("-"),
                name=f"Candidate AI use in {key}",
                purpose=(
                    "UNTRIAGED scan candidate. Replace with the actual purpose and description "
                    "before adding to the register (MAS-AIRM §4.7)."
                ),
                model_type="unknown",
                lifecycle_status=LifecycleStatus.PROPOSED,
                autonomy=AutonomyLevel.ASSISTIVE,
                tags=sorted(set(tags)),
                notes=(
                    f"Detected by airm scan from {len(found)} signal(s): {', '.join(labels)}. "
                    f"Locations: {', '.join(f.location for f in found[:10])}"
                    f"{' ...' if len(found) > 10 else ''}. "
                    f"Scanner output is a candidate for triage, not an inventory entry; "
                    f"{cite('4.3')} makes the designated control function the final arbiter."
                    + (
                        " Agent signals present: confirm the §4.8 fn25 attributes (identifier, "
                        "tools and systems accessible, components, guardrails) and set autonomy."
                        if agentic
                        else ""
                    )
                ),
            )
        )
    return candidates


def signal_catalogue() -> list[dict[str, Any]]:
    """Return the detection rules as plain data, for documentation and review."""
    return [
        {
            "id": s.id,
            "kind": s.kind.value,
            "label": s.label,
            "confidence": s.confidence,
            "citation": s.kind.citation,
            "note": s.note,
        }
        for s in SIGNALS
    ]
