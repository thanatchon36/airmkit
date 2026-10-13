# CLI reference

```
airm version | init | scan | assess | check | evidence | report | gap | crosswalk | clauses | schemas
```

Every command prints the paragraph behind what it says, and ends with the standing disclaimer. Run
`airm <command> --help` for the authoritative option list; this page explains when to reach for
each one.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Nothing adverse found |
| `1` | At least one automated control check **failed** (§5.2 proportionate controls not met) |
| `2` | Usage or input error |

`needs_attestation` does **not** fail the build. By construction it is a question for a person,
and a pipeline that failed on it would teach people to suppress it.

---

## `airm init`

Scaffold a register, and optionally an editable copy of the rubric.

```bash
airm init --institution "Merlion Commercial Bank" --out ai-inventory.yaml --rubric-out rubric.yaml
```

`-i/--institution`, `-o/--out`, `--rubric-out`, `--force`.

## `airm scan`

Shadow-AI discovery over a directory: LLM SDK imports, model endpoints, MCP server configs, agent
frameworks and vendor AI SaaS references (**§4.2 fn21, §4.4 fn22**). Emits candidate inventory
entries for triage.

```bash
airm scan . --out candidates.yaml --min-confidence high --json scan.json
```

`-o/--out`, `--json`, `--min-confidence` (low|medium|high), `--group-by` (directory|file),
`--show`.

!!! warning "Scan output is untrusted data"
    Findings come from files the toolkit did not write. They are never executed, imported or
    treated as configuration; secrets are redacted and symlinks are skipped. Triage candidates
    before merging them into a register.

## `airm assess`

Score Impact, Complexity and Reliance and derive the inherent and residual tiers (**§4.10-§4.13**).

```bash
airm assess -r ai-inventory.yaml --explain          # every score with its reasons
airm assess -r ai-inventory.yaml --write            # write ratings back into the register (§4.7)
airm assess -r ai-inventory.yaml -u kyc-document-agent --json assessment.json
```

`-r/--register`, `--rubric`, `-u/--use-case`, `--explain`, `--write`, `--json`.

## `airm check`

Evaluate the applicable controls for one use case, the whole register, or the institution-level
controls (**§5.2-§5.26, §3.3-§3.5**). This is the command to put in CI.

```bash
airm check -r ai-inventory.yaml --trail evidence/trail.jsonl
airm check -r ai-inventory.yaml --institution
airm check -r ai-inventory.yaml -u kyc-document-agent --all --json results.json
```

`-r/--register`, `-u/--use-case`, `--rubric`, `--controls`, `--trail`, `--institution`, `--all`,
`--json`.

## `airm evidence`

Append a record to the hash-chained trail, or verify it (**§5.23(d), §5.17**). Each `--item` is
hashed, so a file changed after attestation is detectable.

```bash
airm evidence review -u kyc-document-agent -a "model.risk@bank" \
  --item "validation-report=evidence/kyc/validation.md" --outcome pass
airm evidence --verify -t evidence/trail.jsonl
```

`-t/--trail`, `-u/--use-case`, `-a/--actor`, `--item` (repeatable, `name=path`), `--outcome`,
`--severity`, `--verify`.

## `airm report`

Generate the audit-ready pack: board one-pager, inventory register, materiality report, control
applicability statement, gap analysis by effective date, crosswalk coverage, clause index,
third-party assessments and `summary.json`.

```bash
airm report -r examples/synthetic_bank/ai-inventory.yaml \
  --vendors examples/synthetic_bank/third-party-assessments.yaml \
  --trail examples/synthetic_bank/evidence/trail.jsonl \
  -o audit-pack/ --docx
```

`-r/--register`, `-o/--out`, `--rubric`, `--controls`, `--vendors`, `--trail`, `--docx`.

## `airm gap`

Open items grouped by when the underlying clause takes effect (**§1.8**) — the view for a
programme plan: what must be true by 7 October 2027, and what by 7 October 2028.

```bash
airm gap -r ai-inventory.yaml --by-date
```

## `airm crosswalk`

Query the mapping to ISO/IEC 42001, the NIST AI RMF and its GenAI Profile, the EU AI Act, MAS FEAT
and the MAS Information Paper (2024).

```bash
airm crosswalk -c 5.19                                  # what other frameworks say about §5.19
airm crosswalk -f iso_42001                             # everything ISO 42001 maps to
airm crosswalk --ref "Article 14"                        # reverse lookup
airm crosswalk --holding iso_42001,nist_ai_rmf           # residual work if you already hold these
```

`-f/--framework`, `-c/--clause`, `--ref`, `--holding`, `--json`.

## `airm clauses`

The clause index: every paragraph, its effective date, and the controls and module implementing
it. Generated from the catalogue, so it cannot drift.

```bash
airm clauses --section 5 --tag agent --expectations
airm clauses --format markdown -o docs/clause-index.md
```

`-s/--section`, `-t/--tag`, `--expectations`, `--format` (table|markdown), `-o/--out`.

## `airm schemas`

Export a JSON Schema for every format the toolkit reads or writes, so a GRC platform, a
spreadsheet or a service in another language can validate the same files.

```bash
airm schemas --out schemas
```

## `airm version`

Prints the package version and the Guidelines edition the catalogue indexes, with its issue date
and source hash.
