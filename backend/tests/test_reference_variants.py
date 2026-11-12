"""AI reference variants: generated with an LLM, vector stored apart from the references, scored per
report next to (never instead of) the teacher's reference, and listed in the PDF."""

import pytest
from sqlalchemy import func, select

from app.domain.errors import GenerationError
from app.domain.ports.reference_generator_port import ReferenceGeneratorPort
from app.infrastructure.database.models import VarianteReferencia
from app.infrastructure.llm import extract_code, get_reference_generator
from app.main import app

REF_CODE = "#include <stdio.h>\nint main(void) { int n; scanf(\"%d\", &n); printf(\"%d\\n\", n * 2); return 0; }\n"
VARIANT_CODE = "#include <stdio.h>\nint dup(int n) { return n + n; }\nint main(void) { int n; scanf(\"%d\", &n); printf(\"%d\\n\", dup(n)); return 0; }\n"


class FakeGenerator(ReferenceGeneratorPort):
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    async def generate(self, *, enunciado, reference_code, instructions, language):
        self.calls.append((enunciado, reference_code, instructions, language))
        if self.fail:
            raise GenerationError("generation_failed", "boom")
        return VARIANT_CODE


@pytest.fixture
def generator():
    gen = FakeGenerator()
    app.dependency_overrides[get_reference_generator] = lambda: gen
    return gen


async def _setup(client, with_reference=True):
    await client.post("/api/v1/auth/register", json={"email": "var@escom.ipn.mx", "password": "PasswordSegura123!", "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": "var@escom.ipn.mx", "password": "PasswordSegura123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    prob = await client.post("/api/v1/problems/", json={"titulo": "T", "enunciado": "Duplica n", "lenguaje": "c"}, headers=headers)
    pid = prob.json()["id"]
    if with_reference:
        res = await client.post(f"/api/v1/problems/{pid}/references", params={"autor": "Docente", "contenido": REF_CODE}, headers=headers)
        assert res.status_code == 201, res.text
    return headers, pid


async def _variant(client, headers, pid, titulo="Usando funcion"):
    return await client.post(
        f"/api/v1/problems/{pid}/variants", json={"titulo": titulo, "instrucciones": "usa una funcion auxiliar"}, headers=headers
    )


@pytest.mark.asyncio
async def test_variant_is_generated_and_its_vector_never_reaches_reference_queries(client, vector_store, generator):
    headers, pid = await _setup(client)
    res = await _variant(client, headers, pid)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["titulo"] == "Usando funcion" and body["contenido"] == VARIANT_CODE
    # The LLM receives the statement, the teacher's reference and the instructions.
    assert generator.calls == [("Duplica n", REF_CODE, "usa una funcion auxiliar", "c")]
    variant_vec = vector_store.store[body["id"]]
    assert variant_vec["metadata"]["variante_problema_id"] == pid and "problema_id" not in variant_vec["metadata"]
    nearest = await vector_store.query_nearest(vector_store.last_upsert_embedding, pid, top_k=5)
    assert body["id"] not in [m["reference_id"] for m in nearest]


@pytest.mark.asyncio
async def test_variant_limit_and_missing_reference_are_refused(client, db_session, generator):
    headers, pid = await _setup(client)
    for i in range(3):
        assert (await _variant(client, headers, pid, f"V{i}")).status_code == 201
    assert (await _variant(client, headers, pid, "V4")).status_code == 409
    assert (await db_session.execute(select(func.count()).select_from(VarianteReferencia))).scalar_one() == 3

    bare = await client.post("/api/v1/problems/", json={"titulo": "B", "enunciado": "E", "lenguaje": "c"}, headers=headers)
    res = await _variant(client, headers, bare.json()["id"])
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_generation_failure_writes_nothing(client, db_session, vector_store, generator):
    headers, pid = await _setup(client)
    generator.fail = True
    res = await _variant(client, headers, pid)
    assert res.status_code == 503
    assert (await db_session.execute(select(func.count()).select_from(VarianteReferencia))).scalar_one() == 0
    assert all("variante_problema_id" not in v["metadata"] for v in vector_store.store.values())


@pytest.mark.asyncio
async def test_report_carries_variant_metrics_and_pdf_lists_them(client, generator, pdf_text):
    headers, pid = await _setup(client)
    await _variant(client, headers, pid, "Usando funcion")
    await _variant(client, headers, pid, "Version recursiva")
    sub = await client.post(
        f"/api/v1/problems/{pid}/submissions",
        json={"problema_id": pid, "autor": "Alumno", "contenido": VARIANT_CODE}, headers=headers,
    )
    run = await client.post("/api/v1/analysis/run", json={"entrega_id": sub.json()["id"]}, headers=headers)
    assert run.status_code in (200, 201), run.text
    report = run.json()
    assert [v["titulo"] for v in report["variantes"]] == ["Usando funcion", "Version recursiva"]
    # Same code as the variant: the cosine is the maximum, and the headline reference is untouched.
    assert all(v["gcb_similarity"] is not None for v in report["variantes"])
    assert report["referencia_id"] is not None

    again = await client.get(f"/api/v1/analysis/reports/{report['id']}", headers=headers)
    assert len(again.json()["variantes"]) == 2
    pdf = await client.get(f"/api/v1/analysis/reports/{report['id']}/pdf", headers=headers)
    text = pdf_text(pdf.content)
    assert "Usando funcion" in text and "Version recursiva" in text

    # The code view gets each variant's code and metric; the teacher's reference stays the default.
    code = (await client.get(f"/api/v1/analysis/reports/{report['id']}/code", headers=headers)).json()
    assert code["reference_code"] == REF_CODE
    assert [(v["titulo"], v["contenido"]) for v in code["variantes"]] == [
        ("Usando funcion", VARIANT_CODE), ("Version recursiva", VARIANT_CODE)
    ]
    assert all(v["gcb_similarity"] is not None for v in code["variantes"])


@pytest.mark.asyncio
async def test_report_without_variants_has_an_empty_list_and_no_variant_section(client, pdf_text):
    headers, pid = await _setup(client)
    sub = await client.post(
        f"/api/v1/problems/{pid}/submissions", json={"problema_id": pid, "autor": "A", "contenido": REF_CODE}, headers=headers
    )
    report = (await client.post("/api/v1/analysis/run", json={"entrega_id": sub.json()["id"]}, headers=headers)).json()
    assert report["variantes"] == []
    pdf = await client.get(f"/api/v1/analysis/reports/{report['id']}/pdf", headers=headers)
    assert "variantes generadas" not in pdf_text(pdf.content)


@pytest.mark.asyncio
async def test_pdf_of_a_long_submission_splits_across_pages(client, generator, pdf_text):
    """A submission longer than a page used to raise a reportlab LayoutError (one-cell code table)."""
    headers, pid = await _setup(client)
    await _variant(client, headers, pid, "Usando funcion")
    long_code = REF_CODE + "".join(f"int v{i} = {i}; /* linea {i} */\n" for i in range(400))
    sub = await client.post(
        f"/api/v1/problems/{pid}/submissions", json={"problema_id": pid, "autor": "A", "contenido": long_code}, headers=headers
    )
    report = (await client.post("/api/v1/analysis/run", json={"entrega_id": sub.json()["id"]}, headers=headers)).json()
    pdf = await client.get(f"/api/v1/analysis/reports/{report['id']}/pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    text = pdf_text(pdf.content)
    assert "linea 399" in text and "Usando funcion" in text


def test_extract_code_strips_markdown_fences():
    assert extract_code("Aqui:\n```c\nint main(){}\n```\nlisto") == "int main(){}"
    assert extract_code("int main(){}") == "int main(){}"
