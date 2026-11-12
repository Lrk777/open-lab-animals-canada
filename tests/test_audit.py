from pathlib import Path

from olac.audit import rules
from olac.audit.cli import main, render_markdown
from olac.audit.schema import FIELDS, Finding, PaperAudit, verify_evidence

TEXT = (Path(__file__).parent / "fixtures" / "methods_example.txt").read_text()


def test_rules_extract_core_fields():
    a = rules.extract("fixture", TEXT)
    f = a.findings
    assert set(f) == set(FIELDS)
    assert f["sample_size"].reported and f["sample_size"].value == "2"
    assert f["housing_type"].value == "pair"
    assert f["fluid_or_food_control"].reported
    assert f["fluid_control_detail"].reported
    assert f["implant_described"].value == "headpost"
    assert f["ccac_guidelines"].reported
    assert f["randomisation"].reported
    assert not f["blinding"].reported
    assert not f["sample_size_justification"].reported


def test_every_reported_rule_finding_has_verbatim_evidence():
    a = rules.extract("fixture", TEXT)
    checked = verify_evidence(a.model_copy(deep=True), TEXT)
    for k, f in a.findings.items():
        if f.reported:
            assert checked.findings[k].reported, k


def test_verify_evidence_downgrades_fabricated_quotes():
    a = PaperAudit(
        pmcid="x",
        backend="test",
        findings={"blinding": Finding(reported=True, value="yes", evidence="Experimenters were blind to condition.")},
    )
    out = verify_evidence(a, TEXT)
    assert out.findings["blinding"].reported is False
    assert out.findings["blinding"].value == "unverified_quote"


def test_markdown_render_and_exit_code(tmp_path, capsys):
    p = tmp_path / "m.txt"
    p.write_text(TEXT)
    code = main([str(p)])
    out = capsys.readouterr().out
    assert "ARRIVE 2.0 Essential items" in out
    assert "[x]" in out and "[ ]" in out
    assert code == 1  # blinding and sample-size justification are missing
    assert "Suggested additions" in render_markdown(rules.extract("f", TEXT))
