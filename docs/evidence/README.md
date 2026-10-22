# Evidence

Raw output from the first cloud deploys on 2026-09-22, copied from the AgentCore CLI's local logs by [`scripts/export_evidence.py`](../../scripts/export_evidence.py). The script strips colour codes, masks the account ID, runtime ID, role suffix and stack ID, and refuses to write a file if the real account ID survives in any form, including split across lines.

Timestamps are US Central.

| File | What it shows |
|---|---|
| [01-invoke-before-read-policy.txt](01-invoke-before-read-policy.txt) | 19:54. First invocation in Runtime. The execution role has no read permissions, all three tools get AccessDenied, and the agent says so instead of inventing a brief. |
| [02-deploy-add-read-policy.iam-diff.txt](02-deploy-add-read-policy.iam-diff.txt) | 19:58. The policy diff CDK applied: `OpsBriefReadOnlySignals`, three read actions, nothing else. |
| [03-invoke-after-read-policy.txt](03-invoke-after-read-policy.txt) | 19:59. Same prompt, real brief: 2 alarms, no running instances, $2.63 spend for the prior day. |
| [04-deploy-add-model-deny.iam-diff.txt](04-deploy-add-model-deny.iam-diff.txt) | 20:26. The explicit Deny on `InvokeModel` for every model except Nova 2 Lite, applied with `NotResource`. |
| [05-invoke-after-model-deny.txt](05-invoke-after-model-deny.txt) | 20:27. The brief still works after the Deny, so the Deny didn't block the one model the agent needs. |
| [06-status-ready.txt](06-status-ready.txt) | Runtime status `READY`. |

## What this proves and what it doesn't

- **Proven:** the execution role started with no read access (01), the only read access added is the three actions (02), the allowed path works after the Deny (05), and a call to a different model is refused: `simulate-principal-policy` returns `explicitDeny` for Nova Pro and `allowed` for Nova 2 Lite (07, run by hand on 2026-10-22, masked the same way).
- **Not proven:** a live call to another model from inside the Runtime. The simulation evaluates the role's own policies; it doesn't account for SCPs or permission boundaries, which this single account doesn't use.

## Things the output shows that I didn't design for

**The system prompt says no markdown. Every cloud run used markdown.** Nova 2 Lite followed the rules about tools and numbers and ignored the formatting one. A prompt instruction is a request, not a control. If the output format matters (a Slack message, a pager), enforce it in code after the model returns.

**It told me to investigate two alarms that were working as intended.** Both are `TargetTracking ... AlarmLow` alarms from an ECS service's auto scaling policy. They sit in ALARM whenever the service is idle, because that is how target tracking decides to scale in. The numbers in the brief were right. The judgement was wrong, because the agent has no idea which alarms are noise. Two fixes, in order of preference: filter auto scaling alarms in the collector, or pass alarm metadata (who created it, what it drives) so the model can tell the difference. This is the case for an evaluator that checks usefulness, not just faithfulness to the tool output.
