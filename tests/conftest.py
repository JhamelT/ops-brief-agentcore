"""Test setup: no real AWS calls, no real credentials.

collectors.py and main.py build boto3 clients at import time, so a region and
dummy credentials must exist before either module is imported.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ.pop("AWS_PROFILE", None)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "OpsBriefAgent"))
