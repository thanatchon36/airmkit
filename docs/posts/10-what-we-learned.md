We pre-registered 17 hypotheses before running the experiments behind our MAS AI Risk Management toolkit. 7 were refuted. The refutations were the useful part.

**Automation flatters itself depending on the unit of analysis.** At paragraph level 45.1% of expectations look automatable, because a paragraph takes the best class among its controls. Per control, the semi-automated class is largest. We report the pre-registered number and say why we trust the other one more.

**A measurement bug produced a perfect score.** Our guardrail runner used a reasoning model; with thinking enabled the whole token budget went to the thinking channel and the content came back empty. An empty response matches no attack pattern, so every attack scored as "the guardrail held" - 0% attack success, across all five patterns, no error raised. Then five detectors turned out mis-calibrated, one counting a refusal as a success. Both are disclosed in the results and the docstring.

**Proportionality scales rigour, not volume.** Critical-tier use cases needed 91.4 evidence items on average against 92.0 for Medium. Same artefacts, deeper review.

If you only publish what held, you are not reporting - you are advertising.

https://github.com/thanatchon36/airmkit
