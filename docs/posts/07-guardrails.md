§5.15 and fn46 of the MAS AI Risk Management Guidelines require guardrails for generative AI and agents to be tested for effectiveness. We measured five common patterns on a local model against 20 probes - jailbreak, indirect injection, PII leakage, policy evasion - plus a benign in-scope control set.

Attack success:
- no guardrail 75.0%
- system prompt only 37.5%
- deterministic filter 12.5%
- LLM judge 0.0%
- filter + judge 0.0%

Layering and the judge look excellent, though zero out of 16 is a small sample. Then the benign set: over-refusal is 0.0% unguarded, 50.0% with the system prompt and 50.0% layered. The patterns that suppress attacks refuse half of ordinary requests.

Against our pre-registered joint criterion - attack success within the tier limit and over-refusal at or below 5.0% - 0 of 5 patterns qualified. The only pattern with a large reduction at zero over-refusal was the deterministic filter.

A guardrail report without a benign control set is unfalsifiable. Ask for one before you read the attack numbers.

One small local model, n=16 per pattern: a demonstration, not a general estimate.

https://github.com/thanatchon36/airmkit
