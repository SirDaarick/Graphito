"""Shared ScoringService (spec AS1-AS5, AS8, CI8.1; design D8, D9, D15).

Service-level tests over the SQLite session: Channel A is the max Jaccard over the problem's
references (argmax reference, ties to the lowest id), Channel B is CharCNN v2 with abstention, the
dictamen comes only from calibrated flags, and the GraphCodeBERT similarity never decides.
"""

import logging
import uuid
from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.application.services.scoring_service import ScoringService
from app.domain.ports.calibration_port import CalibrationPort
from app.domain.ports.inference_port import StylometryResult
from app.domain.ports.lexical_similarity_port import LexicalSimilarityPort
from app.infrastructure.artifacts.stub_artifacts import STUB_THRESHOLD_A, STUB_THRESHOLD_B, StubCalibration
from app.infrastructure.database.models import (
    CodigoFuente,
    DictamenEnum,
    Docente,
    IndicadorIntegridad,
    Problema,
    ReporteAnalisis,
    TipoCodigoEnum,
)
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.infrastructure.lexical.jaccard import JaccardSimilarity

LONG = "int main(void) {\n    int total = 0;\n    for (int i = 0; i < 10; i++) total += i;\n    return total;\n}\n"


class ScriptedEngine(StubInferenceEngine):
    """Stub embeddings with a scripted Channel B result (legacy keys are never consulted)."""

    def __init__(self, raw: Optional[float] = 0.2, abstained: bool = False):
        self.result = StylometryResult(raw_score=None if abstained else raw, abstained=abstained)
        self.legacy_prob_sintetico = 0.05  # must never surface (CI8.1)

    async def predict_stylometry(self, code):
        return self.result


class TableLexical(LexicalSimilarityPort):
    """Similarity looked up by reference content (non-constant)."""

    def __init__(self, table):
        self.table = table

    def similarity(self, code_a, code_b):
        return self.table[code_b]


class PartialCalibration(CalibrationPort):
    """`ALLOW_UNCALIBRATED`: the named channels have no calibration."""

    engine = "real"

    def __init__(self, missing):
        self.missing = set(missing)
        self.stub = StubCalibration()

    def channel(self, name):
        return None if name in self.missing else self.stub.channel(name)


async def _seed(db, refs=(), code=LONG, ref_ids=None):
    docente = Docente(email=f"{uuid.uuid4().hex}@x.mx", hashed_password="x", nombre="D")
    db.add(docente)
    await db.flush()
    problema = Problema(docente_id=docente.id, titulo="T", enunciado="E")
    db.add(problema)
    await db.flush()
    created = []
    for i, content in enumerate(refs):
        ref = CodigoFuente(problema_id=problema.id, tipo=TipoCodigoEnum.REFERENCIA, autor=f"R{i}", contenido=content)
        if ref_ids:
            ref.id = ref_ids[i]
        db.add(ref)
        created.append(ref)
    entrega = CodigoFuente(problema_id=problema.id, tipo=TipoCodigoEnum.ENTREGA_ALUMNO, autor="S", contenido=code)
    db.add(entrega)
    await db.commit()
    return problema, created, entrega


def _service(vector_store, engine=None, lexical=None, calibration=None):
    return ScoringService(
        engine or ScriptedEngine(), calibration or StubCalibration(), vector_store, lexical or JaccardSimilarity()
    )


@pytest.mark.asyncio
async def test_channel_a_is_max_over_references_with_argmax(db_session, vector_store):
    _, refs, entrega = await _seed(db_session, refs=["ref low", "ref high"])
    service = _service(vector_store, lexical=TableLexical({"ref low": 0.3, "ref high": 0.9}))
    outcome = await service.score(db_session, entrega)
    assert outcome.channel_a.raw == 0.9
    assert outcome.reference_id == str(refs[1].id)
    assert outcome.flag_a is True  # identity stub calibration, threshold 0.5


@pytest.mark.asyncio
async def test_channel_a_ties_resolve_to_lowest_reference_id(db_session, vector_store):
    ids = [uuid.UUID("ffffffff-0000-0000-0000-000000000000"), uuid.UUID("00000000-0000-0000-0000-000000000001")]
    _, refs, entrega = await _seed(db_session, refs=["first", "second"], ref_ids=ids)
    service = _service(vector_store, lexical=TableLexical({"first": 0.4, "second": 0.4}))
    outcome = await service.score(db_session, entrega)
    assert outcome.reference_id == str(ids[1])


@pytest.mark.asyncio
async def test_empty_shingle_stream_does_not_raise(db_session, vector_store):
    _, _, entrega = await _seed(db_session, refs=[LONG], code="   \n  ")
    outcome = await _service(vector_store).score(db_session, entrega)
    assert outcome.estado_canal_a == "VACIO" and outcome.flag_a is None and outcome.channel_a.raw is None


@pytest.mark.asyncio
async def test_no_references_is_sin_referencia_without_chroma(db_session, vector_store):
    _, _, entrega = await _seed(db_session, refs=[])
    outcome = await _service(vector_store, engine=ScriptedEngine(raw=0.2)).score(db_session, entrega)
    assert outcome.estado_canal_a == "SIN_REFERENCIA"
    assert outcome.channel_a.raw is None and outcome.flag_a is None
    assert outcome.dictamen == "SIN_REFERENCIA"
    assert vector_store.queries == [] and outcome.gcb_similarity is None


@pytest.mark.asyncio
async def test_abstained_b_is_null_and_no_evaluable_without_legacy_value(db_session, vector_store):
    _, _, entrega = await _seed(db_session, refs=["ref"])
    service = _service(vector_store, engine=ScriptedEngine(abstained=True), lexical=TableLexical({"ref": 0.1}))
    outcome = await service.score(db_session, entrega)
    assert outcome.estado_canal_b == "ABSTENIDO" and outcome.flag_b is None and outcome.channel_b.calibrated is None
    assert outcome.dictamen == "NO_EVALUABLE"

    reporte = ReporteAnalisis(entrega_id=entrega.id)
    db_session.add(reporte)
    await db_session.flush()
    service.persist(db_session, reporte, outcome, entrega)
    await db_session.commit()
    assert reporte.probabilidad_ia is None and reporte.dictamen == DictamenEnum.NO_EVALUABLE
    assert reporte.discrepancia_score is None
    values = [getattr(reporte, c.key) for c in ReporteAnalisis.__table__.columns]
    assert 0.05 not in values
    rows = (await db_session.execute(
        select(IndicadorIntegridad).where(IndicadorIntegridad.reporte_id == reporte.id)
    )).scalars().all()
    assert not any("CONFORMIDAD" in i.tipo_alerta for i in rows)
    assert not any(i.categoria == "GENERAL" for i in rows)  # no decision indicator without a true flag
    assert not any("5.0%" in i.descripcion or "0.05" in i.descripcion for i in rows)


@pytest.mark.asyncio
async def test_outcome_carries_stub_thresholds_and_no_shas(db_session, vector_store):
    _, _, entrega = await _seed(db_session, refs=["ref"])
    outcome = await _service(vector_store, lexical=TableLexical({"ref": 0.7})).score(db_session, entrega)
    assert outcome.engine == "stub"
    assert outcome.channel_a.threshold == STUB_THRESHOLD_A and outcome.channel_b.threshold == STUB_THRESHOLD_B
    assert outcome.channel_a.calibration_sha256 is None and outcome.channel_b.calibration_sha256 is None
    assert outcome.provenance["checkpoint_sha_b"] is None


@pytest.mark.asyncio
async def test_uncalibrated_channels_report_raw_and_no_flags(db_session, vector_store):
    _, _, entrega = await _seed(db_session, refs=["ref"])
    service = _service(
        vector_store, engine=ScriptedEngine(raw=0.9), lexical=TableLexical({"ref": 0.8}),
        calibration=PartialCalibration({"a", "b"}),
    )
    outcome = await service.score(db_session, entrega)
    assert outcome.flag_a is None and outcome.flag_b is None
    assert outcome.estado_canal_a == outcome.estado_canal_b == "NO_CALIBRADO"
    assert outcome.channel_a.raw == 0.8 and outcome.channel_b.raw == 0.9
    assert outcome.dictamen == "NO_EVALUABLE" and outcome.uncalibrated

    only_a = _service(
        vector_store, engine=ScriptedEngine(raw=0.1), lexical=TableLexical({"ref": 0.8}),
        calibration=PartialCalibration({"a"}),
    )
    outcome = await only_a.score(db_session, entrega)
    assert outcome.flag_a is None and outcome.estado_canal_a == "NO_CALIBRADO"
    assert outcome.dictamen == "NO_EVALUABLE"


@pytest.mark.asyncio
async def test_pinned_reference_from_another_problem_is_422(db_session, vector_store):
    _, other_refs, _ = await _seed(db_session, refs=["other problem ref"])
    _, _, entrega = await _seed(db_session, refs=["ref"])
    with pytest.raises(HTTPException) as exc:
        await _service(vector_store).score(db_session, entrega, referencia_id=other_refs[0].id)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_pinned_reference_restricts_channel_a(db_session, vector_store):
    _, refs, entrega = await _seed(db_session, refs=["ref low", "ref high"])
    service = _service(vector_store, lexical=TableLexical({"ref low": 0.3, "ref high": 0.9}))
    outcome = await service.score(db_session, entrega, referencia_id=refs[0].id)
    assert outcome.channel_a.raw == 0.3 and outcome.reference_id == str(refs[0].id)


@pytest.mark.asyncio
async def test_gcb_never_changes_flags_or_dictamen(db_session, vector_store, monkeypatch):
    _, _, entrega = await _seed(db_session, refs=["ref"])
    service = _service(vector_store, lexical=TableLexical({"ref": 0.6}))
    outcomes = []
    for sim in (0.99, 0.0):
        async def fixed(embedding, problema_id, top_k=1, sim=sim):
            return [{"reference_id": "x", "similarity": sim, "distance": 1 - sim, "metadata": {}}]

        monkeypatch.setattr(vector_store, "query_nearest", fixed)
        outcomes.append(await service.score(db_session, entrega))
    a, b = outcomes
    assert (a.gcb_similarity, b.gcb_similarity) == (0.99, 0.0)
    assert (a.flag_a, a.flag_b, a.dictamen) == (b.flag_a, b.flag_b, b.dictamen)


@pytest.mark.asyncio
async def test_gcb_runtime_error_gives_null_similarity(db_session, vector_store):
    _, _, entrega = await _seed(db_session, refs=["ref"])
    vector_store.fail = True
    outcome = await _service(vector_store, lexical=TableLexical({"ref": 0.6})).score(db_session, entrega)
    assert outcome.gcb_similarity is None and outcome.provenance["gcb_estado"] == "ERROR"
    assert outcome.dictamen == "REVISION_SEMANTICA"


def test_client_thresholds_are_ignored_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        ScoringService.warn_client_thresholds(0.01, 0.01)
    assert "ignored" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ScoringService.warn_client_thresholds(None, None)
    assert caplog.text == ""


def test_indicators_only_for_true_flags():
    from app.domain.scoring import ChannelResult, ScoringOutcome

    neg = ChannelResult.evaluated(raw=0.1, calibrated=0.1, threshold=0.5, threshold_key="k", calibration_sha256=None)
    pos = ChannelResult.evaluated(raw=0.9, calibrated=0.9, threshold=0.5, threshold_key="k", calibration_sha256=None)
    sin_ref = ChannelResult.not_evaluated("SIN_REFERENCIA")
    abst = ChannelResult.not_evaluated("ABSTENCION")
    assert ScoringService.build_indicators(ScoringOutcome.build(neg, neg)) == []
    assert ScoringService.build_indicators(ScoringOutcome.build(sin_ref, neg)) == []
    assert ScoringService.build_indicators(ScoringOutcome.build(neg, abst)) == []
    assert [i["tipo_alerta"] for i in ScoringService.build_indicators(ScoringOutcome.build(pos, neg))] == ["CONVERGENCIA_ESTRUCTURAL"]
    assert [i["tipo_alerta"] for i in ScoringService.build_indicators(ScoringOutcome.build(neg, pos))] == ["PATRON_SINTETICO"]
    assert [i["tipo_alerta"] for i in ScoringService.build_indicators(ScoringOutcome.build(pos, pos))] == ["DISCREPANCIA_ESTILOMETRICA"]
