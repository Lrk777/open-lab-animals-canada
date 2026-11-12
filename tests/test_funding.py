from olac.ingest.funding import _lexicon, classify

LEX = _lexicon()


def test_lab_primate_research_is_detected():
    assert "nhp_research" in classify("Neural mechanisms of working memory in rhesus macaques", LEX)
    assert "nhp_research" in classify("Recordings from awake behaving monkeys in area LIP", LEX)


def test_field_primatology_and_mpox_are_excluded():
    assert "nhp_research" not in classify("Foraging ecology of wild primates at a field station", LEX)
    assert "nhp_research" not in classify("Monkeypox transmission dynamics in Central Africa", LEX)


def test_non_animal_methods():
    assert "non_animal_methods" in classify("Patient-derived organoids for drug screening", LEX)
    assert "non_animal_methods" in classify("A brain organ-on-a-chip platform", LEX)
    assert classify("Hydrology of northern rivers", LEX) == []


def test_computational_neuro_requires_brain_context():
    assert "computational_neuro" not in classify("Deep neural networks for blueberry harvesting", LEX)
    assert "computational_neuro" in classify("Deep neural networks as models of the primate visual cortex", LEX)
