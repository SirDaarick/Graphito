"""R2: the vector store only ever sees the 768-dim semantic embedding."""

import pytest
from httpx import AsyncClient

from app.infrastructure.inference import get_inference_engine
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.main import app

REF_CODE = """
#include <stdio.h>
int main() { int n; scanf("%d", &n); printf("%d\\n", n * 2); return 0; }
"""
STUDENT_CODE = """
#include <stdio.h>
int main() { int x; scanf("%d", &x); printf("%d\\n", x + x); return 0; }
"""


class FixedAiProbEngine(StubInferenceEngine):
    def __init__(self, ai_prob: float):
        self._ai_prob = ai_prob

    async def predict_synthetic_prob(self, code: str) -> float:
        return self._ai_prob


async def _setup_problem_with_reference(client: AsyncClient, suffix: str):
    email = f"dims_{suffix}@escom.ipn.mx"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "PasswordSegura123!", "nombre": "Prof"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "PasswordSegura123!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    prob = await client.post(
        "/api/v1/problems/",
        json={"titulo": "Doble", "enunciado": "Duplica un entero leido de la entrada.", "lenguaje": "c"},
        headers=headers,
    )
    problema_id = prob.json()["id"]
    ref = await client.post(
        f"/api/v1/problems/{problema_id}/references",
        params={"autor": "Docente", "contenido": REF_CODE, "lenguaje": "c"},
        headers=headers,
    )
    assert ref.status_code == 201, ref.text
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": STUDENT_CODE, "lenguaje": "c"},
        headers=headers,
    )
    assert sub.status_code == 201, sub.text
    return headers, sub.json()["id"]


@pytest.mark.asyncio
async def test_reference_upsert_is_768_dim(client: AsyncClient, vector_store):
    await _setup_problem_with_reference(client, "upsert")
    assert vector_store.last_upsert_embedding is not None
    assert len(vector_store.last_upsert_embedding) == 768


@pytest.mark.asyncio
async def test_analysis_query_is_768_dim_and_independent_of_ai_prob(client: AsyncClient, vector_store):
    headers, entrega_id = await _setup_problem_with_reference(client, "query")

    queries = []
    for ai_prob in (0.05, 0.95):
        app.dependency_overrides[get_inference_engine] = lambda p=ai_prob: FixedAiProbEngine(p)
        res = await client.post(
            "/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers
        )
        assert res.status_code == 201, res.text
        queries.append(vector_store.last_query_embedding)

    assert len(queries[0]) == 768
    assert queries[0] == queries[1], "query embedding must not depend on ai_prob (R2.5)"


@pytest.mark.parametrize("dim", [767, 769])
@pytest.mark.asyncio
async def test_chroma_adapter_rejects_wrong_dimension(dim):
    pytest.importorskip("chromadb")
    from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter

    class _Boom:
        def upsert(self, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("collection must not be called with a bad dimension")

        query = upsert

    adapter = ChromaVectorStoreAdapter.__new__(ChromaVectorStoreAdapter)
    adapter.collection = _Boom()

    with pytest.raises(ValueError):
        await adapter.upsert_reference("id", [0.0] * dim, {"problema_id": 1})
    with pytest.raises(ValueError):
        await adapter.query_nearest([0.0] * dim, problema_id=1)
