"""Copy AgentCore CLI logs into docs/evidence/ with identifiers masked.

The CLI writes deploy/invoke/status logs to agentcore/.cli/logs/, which is
gitignored because the logs carry the account ID, runtime ID and role names.
This script copies the runs worth showing, strips ANSI colour codes, and
masks anything that identifies the account before it lands in the repo.

Usage: python3 scripts/export_evidence.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "agentcore" / ".cli" / "logs"
OUT = ROOT / "docs" / "evidence"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
MASKS = [
    (re.compile(r"\b\d{12}\b"), "<ACCOUNT_ID>"),
    (re.compile(r"(OpsBriefAgent-)[A-Za-z0-9]{10}\b"), r"\1<RUNTIME_SUFFIX>"),
    (re.compile(r"(ApplicationAgentOpsBriefA-)[A-Za-z0-9]{12}\b"), r"\1<ROLE_SUFFIX>"),
    (re.compile(r"BedrockAgentCore-[0-9a-f-]{36}"), "BedrockAgentCore-<SESSION_ID>"),
    (re.compile(r"stack/([\w-]+)/[0-9a-f-]{36}"), r"stack/\1/<STACK_ID>"),
]

# (output name, source log, optional line filter)
RUNS = [
    ("01-invoke-before-read-policy.txt", "invoke/invoke-OpsBriefAgent-20260922-195419.log", None),
    ("02-deploy-add-read-policy.iam-diff.txt", "deploy/deploy-20260922-195801.log", "iam"),
    ("03-invoke-after-read-policy.txt", "invoke/invoke-OpsBriefAgent-20260922-195927.log", None),
    ("04-deploy-add-model-deny.iam-diff.txt", "deploy/deploy-20260922-202626.log", "iam"),
    ("05-invoke-after-model-deny.txt", "invoke/invoke-OpsBriefAgent-20260922-202718.log", None),
    ("06-status-ready.txt", "status/status-20260922-200000.log", None),
]


def mask(text: str) -> str:
    text = ANSI.sub("", text)
    for pattern, repl in MASKS:
        text = pattern.sub(repl, text)
    return text


def iam_sections(text: str) -> str:
    """Keep the execution-role policy diff and the deploy result lines.

    The CDK "IAM Statement Changes" table is skipped on purpose: it wraps ARNs
    across table cells, which splits the account ID so a regex can't mask it.
    The policy document diff shows the same change with ARNs on one line.
    """
    keep, grabbing = [], False
    for line in text.splitlines():
        if "AWS::IAM::Policy" in line and "[~]" in line:
            grabbing = True
        if grabbing:
            keep.append(line)
            if line.startswith("\u2500\u2500\u2500"):  # end of the diff block
                grabbing = False
                keep.append("")
        elif any(k in line for k in ("Deployment time", "COMPLETED", "UPDATE_COMPLETE | AWS::IAM::Policy")):
            keep.append(line)
    return "\n".join(keep) + "\n"


def account_digits_leak(text: str) -> bool:
    """True if the real account ID appears anywhere, even split across lines."""
    targets = ROOT / "agentcore" / "aws-targets.json"
    if not targets.exists():
        return False
    ids = re.findall(r"\d{12}", targets.read_text())
    digits = re.sub(r"\D", "", text)
    return any(i in digits for i in ids)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, src, mode in RUNS:
        path = LOGS / src
        if not path.exists():
            print(f"skip (missing): {src}")
            continue
        text = path.read_text(errors="replace")
        if mode == "iam":
            text = iam_sections(text)
        text = mask(text)
        if re.search(r"\b\d{12}\b", text) or account_digits_leak(text):
            print(f"refusing to write {name}: unmasked 12-digit number remains")
            return 1
        (OUT / name).write_text(text)
        print(f"wrote docs/evidence/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
