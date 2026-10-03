"""The generated change tests must all pass their self-check."""

import json

import pytest

from navigator.paths import CHANGES_OUT


@pytest.mark.skipif(not CHANGES_OUT.exists(), reason="run `make outputs` first")
def test_every_change_test_passes_its_self_check():
    changes = json.loads(CHANGES_OUT.read_text())
    failures = {tid: c["self_check"]["detail"] for tid, c in changes.items() if not c["self_check"]["passed"]}
    assert not failures, failures
