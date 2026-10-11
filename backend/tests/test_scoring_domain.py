"""Pure decision matrix (spec AS4.1, AS4.3, AS4.4, AS3.2; design decision matrix, D-B).

Precedence (spec is the contract; design open question resolved as "a positive flag wins"):
a positive flag on an evaluable channel is never hidden; with no positive flag, `SIN_ALERTAS`
needs both channels evaluated and negative, `SIN_REFERENCIA` needs A without references and B
evaluated and negative, and everything else is `NO_EVALUABLE`.
"""

import ast
from pathlib import Path

import pytest

from app.domain import scoring
from app.domain.errors import ArtifactError, GraphitoError, InferenceError, NotReadyError, VectorStoreError
from app.domain.scoring import ChannelResult, ScoringOutcome, decide

DOMAIN = Path(__file__).resolve().parents[1] / "app" / "domain"

A_FLAG = ChannelResult.evaluated(raw=0.9, calibrated=0.8, threshold=0.5, threshold_key="fpr_0.05", calibration_sha256="a" * 64)
A_NOFLAG = ChannelResult.evaluated(raw=0.1, calibrated=0.1, threshold=0.5, threshold_key="fpr_0.05", calibration_sha256="a" * 64)
A_SIN_REF = ChannelResult.not_evaluated(scoring.A_SIN_REFERENCIA)
A_VACIO = ChannelResult.not_evaluated(scoring.A_VACIO, raw=None)
A_SIN_CAL = ChannelResult.not_evaluated(scoring.SIN_CALIBRACION, raw=0.4)
B_FLAG = ChannelResult.evaluated(raw=2.0, calibrated=0.9, threshold=0.1715, threshold_key="fpr_0.01", calibration_sha256="b" * 64)
B_NOFLAG = ChannelResult.evaluated(raw=-3.0, calibrated=0.05, threshold=0.1715, threshold_key="fpr_0.01", calibration_sha256="b" * 64)
B_ABST = ChannelResult.not_evaluated(scoring.B_ABSTENCION)
B_SIN_CAL = ChannelResult.not_evaluated(scoring.SIN_CALIBRACION, raw=1.2)

A_STATES = {"A+": A_FLAG, "A-": A_NOFLAG, "A_SIN_REF": A_SIN_REF, "A_VACIO": A_VACIO, "A_SIN_CAL": A_SIN_CAL}
B_STATES = {"B+": B_FLAG, "B-": B_NOFLAG, "B_ABST": B_ABST, "B_SIN_CAL": B_SIN_CAL}

# All 20 A x B combinations (5 A states x 4 B states).
MATRIX = {
    ("A+", "B+"): "DISCREPANCIA_DUAL",
    ("A+", "B-"): "REVISION_SEMANTICA",
    ("A+", "B_ABST"): "REVISION_SEMANTICA",
    ("A+", "B_SIN_CAL"): "REVISION_SEMANTICA",
    ("A-", "B+"): "REVISION_ESTILOMETRICA",
    ("A-", "B-"): "SIN_ALERTAS",
    ("A-", "B_ABST"): "NO_EVALUABLE",
    ("A-", "B_SIN_CAL"): "NO_EVALUABLE",
    ("A_SIN_REF", "B+"): "REVISION_ESTILOMETRICA",
    ("A_SIN_REF", "B-"): "SIN_REFERENCIA",
    ("A_SIN_REF", "B_ABST"): "NO_EVALUABLE",
    ("A_SIN_REF", "B_SIN_CAL"): "NO_EVALUABLE",
    ("A_VACIO", "B+"): "REVISION_ESTILOMETRICA",
    ("A_VACIO", "B-"): "NO_EVALUABLE",
    ("A_VACIO", "B_ABST"): "NO_EVALUABLE",
    ("A_VACIO", "B_SIN_CAL"): "NO_EVALUABLE",
    ("A_SIN_CAL", "B+"): "REVISION_ESTILOMETRICA",
    ("A_SIN_CAL", "B-"): "NO_EVALUABLE",
    ("A_SIN_CAL", "B_ABST"): "NO_EVALUABLE",
    ("A_SIN_CAL", "B_SIN_CAL"): "NO_EVALUABLE",
}


def test_matrix_covers_all_twenty_combinations():
    assert set(MATRIX) == {(a, b) for a in A_STATES for b in B_STATES}
    assert len(MATRIX) == 20


@pytest.mark.parametrize(("a", "b"), sorted(MATRIX), ids=[f"{a}|{b}" for a, b in sorted(MATRIX)])
def test_decide_matrix(a, b):
    assert decide(A_STATES[a], B_STATES[b]) == MATRIX[(a, b)]


@pytest.mark.parametrize(("a", "b"), sorted(MATRIX))
def test_positive_flag_is_never_hidden(a, b):
    verdict = decide(A_STATES[a], B_STATES[b])
    if A_STATES[a].flag:
        assert verdict in {"DISCREPANCIA_DUAL", "REVISION_SEMANTICA"}
    if B_STATES[b].flag:
        assert verdict in {"DISCREPANCIA_DUAL", "REVISION_ESTILOMETRICA"}


def test_sin_alertas_requires_both_channels_evaluated_and_negative():
    for (a, b), verdict in MATRIX.items():
        if verdict == "SIN_ALERTAS":
            assert (a, b) == ("A-", "B-")


def test_spec_scenarios_one_per_table_row():
    # AS4.1 scenario list, in the spec's order.
    rows = [
        (A_FLAG, B_FLAG, "DISCREPANCIA_DUAL"), (A_FLAG, B_NOFLAG, "REVISION_SEMANTICA"),
        (A_FLAG, B_ABST, "REVISION_SEMANTICA"), (A_NOFLAG, B_FLAG, "REVISION_ESTILOMETRICA"),
        (A_SIN_REF, B_FLAG, "REVISION_ESTILOMETRICA"), (A_NOFLAG, B_ABST, "NO_EVALUABLE"),
        (A_SIN_REF, B_ABST, "NO_EVALUABLE"), (A_SIN_REF, B_NOFLAG, "SIN_REFERENCIA"),
        (A_NOFLAG, B_NOFLAG, "SIN_ALERTAS"),
    ]
    for a, b, expected in rows:
        assert decide(a, b) == expected


def test_flag_is_calibrated_score_at_or_above_threshold():
    at = ChannelResult.evaluated(raw=0.3, calibrated=0.5, threshold=0.5, threshold_key="k", calibration_sha256=None)
    below = ChannelResult.evaluated(raw=0.3, calibrated=0.4999, threshold=0.5, threshold_key="k", calibration_sha256=None)
    assert at.flag is True and below.flag is False


def test_abstained_b_has_null_score_flag_and_abstenido_state():
    outcome = ScoringOutcome.build(A_NOFLAG, ChannelResult.not_evaluated(scoring.B_ABSTENCION))
    assert outcome.channel_b.raw is None and outcome.channel_b.calibrated is None
    assert outcome.channel_b.flag is None
    assert outcome.estado_canal_b == "ABSTENIDO"
    assert outcome.dictamen == "NO_EVALUABLE"


def test_uncalibrated_channel_reports_raw_score_without_flag():
    # AS4.3: raw score reported, flag null, state NO_CALIBRADO, verdict NO_EVALUABLE (no positive flag).
    outcome = ScoringOutcome.build(A_SIN_CAL, B_NOFLAG)
    assert outcome.channel_a.raw == 0.4 and outcome.channel_a.flag is None
    assert outcome.estado_canal_a == "NO_CALIBRADO"
    assert outcome.dictamen == "NO_EVALUABLE"
    assert outcome.uncalibrated is True
    assert ScoringOutcome.build(A_NOFLAG, B_NOFLAG).uncalibrated is False


def test_persisted_state_strings_come_from_one_mapping():
    # D-B: spec strings persisted; one mapping constant from the design states.
    assert scoring.PERSISTED_STATE == {
        "OK": "EVALUADO",
        "SIN_REFERENCIA": "SIN_REFERENCIA",
        "VACIO": "VACIO",
        "SIN_CALIBRACION": "NO_CALIBRADO",
        "ABSTENCION": "ABSTENIDO",
    }
    outcome = ScoringOutcome.build(A_SIN_REF, B_FLAG)
    assert (outcome.estado_canal_a, outcome.estado_canal_b) == ("SIN_REFERENCIA", "EVALUADO")
    assert outcome.flag_a is None and outcome.flag_b is True


def test_indicators_only_for_true_flags():
    # AS4.4: no CONFORMIDAD_BASE (or any) indicator for NO_EVALUABLE / SIN_REFERENCIA / SIN_ALERTAS.
    assert ScoringOutcome.build(A_SIN_REF, B_NOFLAG).flagged_channels == ()
    assert ScoringOutcome.build(A_NOFLAG, B_ABST).flagged_channels == ()
    assert ScoringOutcome.build(A_FLAG, B_ABST).flagged_channels == ("a",)
    assert ScoringOutcome.build(A_FLAG, B_FLAG).flagged_channels == ("a", "b")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"estado": "OK", "raw": 0.1, "calibrated": None, "flag": None},
        {"estado": "ABSTENCION", "raw": None, "calibrated": None, "flag": False},
        {"estado": "SIN_REFERENCIA", "raw": None, "calibrated": 0.3, "flag": None},
        {"estado": "BOGUS", "raw": None, "calibrated": None, "flag": None},
    ],
)
def test_channel_result_rejects_inconsistent_states(kwargs):
    with pytest.raises(ValueError):
        ChannelResult(threshold=None, threshold_key=None, calibration_sha256=None, **kwargs)


def test_channel_specific_states_are_enforced():
    with pytest.raises(ValueError):
        decide(B_ABST, B_NOFLAG)  # ABSTENCION is a B-only state
    with pytest.raises(ValueError):
        decide(A_NOFLAG, A_SIN_REF)  # SIN_REFERENCIA is an A-only state


def test_typed_errors_carry_a_reason():
    for cls in (ArtifactError, InferenceError, VectorStoreError, NotReadyError):
        err = cls("some_reason", "details")
        assert isinstance(err, GraphitoError) and err.reason == "some_reason"


def test_infrastructure_artifact_error_is_the_domain_error():
    from app.infrastructure.artifacts import ArtifactError as InfraArtifactError

    assert InfraArtifactError is ArtifactError


FORBIDDEN_PREFIXES = (
    "fastapi", "sqlalchemy", "pydantic", "starlette", "torch", "numpy", "sklearn", "transformers",
    "chromadb", "models", "app.infrastructure", "app.application", "app.presentation", "app.config",
)


def test_domain_imports_no_framework():
    offenders = []
    for path in sorted(DOMAIN.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith(FORBIDDEN_PREFIXES):
                    offenders.append(f"{path.name}: {name}")
    assert not offenders, offenders


def test_inference_port_shape():
    from app.domain.ports.inference_port import InferencePort, Readiness, StylometryResult

    abstract = InferencePort.__abstractmethods__
    assert {"readiness", "extract_semantic_embedding", "predict_stylometry"} <= abstract
    assert "compute_decision" not in dir(InferencePort)
    assert "generate_hybrid_embedding" not in dir(InferencePort)
    assert StylometryResult(raw_score=None, abstained=True).abstained is True
    assert Readiness(ready=False, reason="artifact_error").reason == "artifact_error"


def test_calibration_and_lexical_ports_exist():
    from app.domain.ports.calibration_port import CalibratedChannel, CalibrationPort
    from app.domain.ports.lexical_similarity_port import LexicalSimilarityPort

    assert {"channel"} <= CalibrationPort.__abstractmethods__
    assert {"similarity"} <= LexicalSimilarityPort.__abstractmethods__
    assert hasattr(CalibratedChannel, "calibrate")
