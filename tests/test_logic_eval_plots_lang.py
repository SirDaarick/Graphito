"""Tests for the label language option of the G1-G5 logic evaluation plots."""

import matplotlib.pyplot as plt
import numpy as np
import pytest

from models.logic_eval import plots as P


def _texts(monkeypatch):
    """Collect every text drawn on figures saved by the plot functions."""
    seen = []

    def fake_savefig(path, *args, **kwargs):
        fig = plt.gcf()
        fig.canvas.draw()  # tick labels only get their text at draw time
        for t in fig.findobj(match=lambda o: hasattr(o, "get_text")):
            if t.get_text():
                seen.append(t.get_text())
        path.write_bytes(b"png")

    monkeypatch.setattr(P.plt, "savefig", fake_savefig)
    return seen


def _draw_all(tmp_path, lang):
    labels = ["A", "A", "B", "B"]
    sim = np.eye(4)
    P.plot_g1_heatmap({"v2": sim}, labels, tmp_path / "g1.png", lang=lang)
    P.plot_g3_map_at_r({"v2": {"value": 0.5, "ci95": [0.4, 0.6]}}, 0.002, tmp_path / "g3.png", lang=lang)
    points = [{"sim_to_ref": 0.9, "pass_rate": 1.0}, {"sim_to_ref": 0.2, "pass_rate": 0.0}]
    P.plot_g4_correctness({"v2": points}, tmp_path / "g4.png", lang=lang)
    ranked = [{"student": "s1", "last_test_results": "3/3", "pasa": True, "sim": 0.8}]
    P.plot_g5_teacher_view(ranked, "A2016/Z1/Z1", tmp_path / "g5.png", lang=lang)


def test_default_language_keeps_english_labels(tmp_path, monkeypatch):
    seen = _texts(monkeypatch)
    _draw_all(tmp_path, "en")
    assert "G1: Similarity Heatmap Ordered by Assignment" in seen
    assert "Random baseline (0.002)" in seen
    assert "Pass (1)" in seen and "Fail (1)" in seen
    assert "Passing" in seen


def test_spanish_labels(tmp_path, monkeypatch):
    seen = _texts(monkeypatch)
    _draw_all(tmp_path, "es")
    assert "G1: Mapa de calor de similitud ordenado por tarea" in seen
    assert "Línea base aleatoria (0.002)" in seen
    assert "Pasa todas (1)" in seen and "Falla todas (1)" in seen
    assert "G5: Ranking de inspección docente — A2016/Z1/Z1" in seen
    assert not any("Similarity" in t for t in seen)


def test_languages_define_the_same_keys():
    assert set(P.LABELS["en"]) == set(P.LABELS["es"])


def test_unknown_language_raises(tmp_path):
    with pytest.raises(KeyError):
        P.plot_g3_map_at_r({"v2": {"value": 0.5}}, 0.0, tmp_path / "g3.png", lang="fr")
