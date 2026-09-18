import pytest
from storage import usage
from config import AUTO_SETTLE_LIMIT


def test_usage_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "LOCAL_FILE", str(tmp_path / "u.json"))
    assert usage.settle_remaining() == AUTO_SETTLE_LIMIT
    usage.settle_increment(3)
    assert usage.settle_remaining() == AUTO_SETTLE_LIMIT - 3
    usage.settle_reset()
    assert usage.settle_remaining() == AUTO_SETTLE_LIMIT
