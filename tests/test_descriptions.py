import json
import re

from config import DESCRIPTIONS

COMPLETE = (DESCRIPTIONS / "re21_complete.txt").read_text()
INCOMPLETE = (DESCRIPTIONS / "re21_incomplete.txt").read_text()
LOG = json.loads((DESCRIPTIONS / "re21_descriptions.json").read_text())


def test_no_formulas_or_symbols_leak():
    for text in (COMPLETE, INCOMPLETE):
        assert not re.search(r"sqrt|√|x_?\d|f_?\d|=", text, flags=re.IGNORECASE)


def test_complete_states_all_parameter_values():
    for needle in ("200 cm", "10 kN", "2 x 10^5 kN/cm^2", "10 kN/cm^2", "cross-sectional area", "volume", "displacement"):
        assert needle in COMPLETE


def test_incomplete_omits_what_the_log_says():
    omitted = [f for f in LOG["facts"] if f["incomplete"].startswith("OMITTED")]
    assert {gid for f in omitted for gid in f["ground_truth_ids"]} >= {"L", "F", "E", "sigma"}
    for needle in ("200", "kN", "elastic", "stress", "length", "force", "material"):
        assert needle not in INCOMPLETE.lower()
    for needle in ("cross-sectional area", "volume", "displacement", "four bars"):
        assert needle in INCOMPLETE
