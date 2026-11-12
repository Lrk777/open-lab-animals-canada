import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from olac.audit import evaluate, llm
from olac.audit.schema import FIELDS

TEXT = (Path(__file__).parent / "fixtures" / "methods_example.txt").read_text()


class FakeClient:
    """Stands in for openai.OpenAI; returns one true quote and one fabricated quote."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        assert kwargs["response_format"]["json_schema"]["strict"] is True
        out = {k: {"reported": False, "value": None, "evidence": None, "confidence": 0.9} for k in FIELDS}
        out["housing_type"] = {"reported": True, "value": "pair", "confidence": 0.95,
                               "evidence": "were pair housed with environmental enrichment"}
        out["blinding"] = {"reported": True, "value": "yes", "confidence": 0.6,
                           "evidence": "The experimenter was blind to the condition."}
        msg = SimpleNamespace(content=json.dumps(out))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_llm_extract_keeps_real_quotes_and_drops_fabricated_ones():
    a = llm.extract("fixture", TEXT, model="fake", client=FakeClient())
    assert a.backend == "llm:fake"
    assert a.findings["housing_type"].reported and a.findings["housing_type"].value == "pair"
    assert not a.findings["blinding"].reported
    assert a.findings["blinding"].value == "unverified_quote"


def test_evaluate_computes_metrics(tmp_path, monkeypatch):
    gold_dir, proc = tmp_path / "gold", tmp_path / "processed"
    gold_dir.mkdir()
    proc.mkdir()
    gold = pd.DataFrame({"pmcid": ["p1", "p1", "p2", "p2"], "field": ["housing_type", "blinding"] * 2,
                         "reported": ["TRUE", "FALSE", "TRUE", "TRUE"]})
    gold.to_csv(gold_dir / "labels_A.csv", index=False)
    gold.assign(reported=["TRUE", "FALSE", "FALSE", "TRUE"]).to_csv(gold_dir / "labels_B.csv", index=False)
    pd.DataFrame({"pmcid": ["p1", "p1", "p2", "p2"], "backend": "rules", "field": ["housing_type", "blinding"] * 2,
                  "reported": [True, False, True, False], "confidence": None}).to_csv(proc / "audit_rules.csv", index=False)
    monkeypatch.setattr(evaluate, "GOLD", gold_dir)
    monkeypatch.setattr(evaluate, "PROCESSED", proc)
    ag = evaluate.agreement()
    assert set(ag.field) == {"housing_type", "blinding"}
    s = evaluate.evaluate()
    row = s.iloc[0]
    assert row.backend == "rules" and row.n_papers == 2
    assert row.micro_precision == 1.0 and abs(row.micro_recall - 2 / 3) < 1e-9
