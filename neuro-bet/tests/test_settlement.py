import pytest
from betting.settlement import determine_outcome


@pytest.mark.parametrize("market,pick,hg,ag,expected", [
    ("1X2", "П1", 2, 0, "won"),
    ("1X2", "X", 1, 1, "won"),
    ("1X2", "П2", 0, 2, "won"),
    ("OU", "ТБ 2.5", 2, 1, "won"),
    ("OU", "ТМ 2.5", 1, 1, "won"),
    ("AH", "Ф1(-0.5)", 2, 1, "won"),
    ("AH", "Ф1(-0.5)", 1, 1, "lost"),
    ("AH", "Ф1(0)", 1, 1, "push"),
    ("BTTS", "BTTS да", 1, 1, "won"),
    ("BTTS", "BTTS нет", 1, 0, "won"),
    ("DC", "1X", 1, 1, "won"),
    ("DC", "12", 1, 1, "lost"),
])
def test_outcomes(market, pick, hg, ag, expected):
    out, _ = determine_outcome(market, pick, hg, ag)
    assert out == expected


def test_unknown_market():
    out, reason = determine_outcome("XYZ", "П1", 1, 0)
    assert out is None
    assert "unknown" in reason
