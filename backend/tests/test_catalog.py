import pytest
from httpx import AsyncClient

CATALOG = "/api/v1/catalog/"


async def _headers(client: AsyncClient, email: str = "catalogo@escom.ipn.mx") -> dict:
    payload = {"email": email, "password": "PasswordSegura123!", "nombre": "Prof. Catalogo"}
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": payload["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _find_id(client: AsyncClient, headers: dict, nombre_archivo: str) -> str:
    res = await client.get(CATALOG, headers=headers)
    for subject in res.json():
        for unit in subject["unidades"]:
            for program in unit["programas"]:
                if program["nombre_archivo"] == nombre_archivo:
                    return program["id"]
    raise AssertionError(f"{nombre_archivo} not in catalog")


CPP_FILE = "24_arbol_binario_inorden_iterativo.cpp"
C_FILE = "23_arbol_binario_recorridos_recursivo.c"


@pytest.mark.asyncio
async def test_list_catalog_grouped_without_code(client: AsyncClient):
    headers = await _headers(client)
    res = await client.get(CATALOG, headers=headers)
    assert res.status_code == 200, res.text
    subjects = res.json()
    assert len(subjects) == 3
    assert sum(s["total"] for s in subjects) == 84
    assert not any("paradigmas" in s["materia"] for s in subjects)

    ids = []
    for subject in subjects:
        count = 0
        for unit in subject["unidades"]:
            assert unit["unidad_nombre"]
            for program in unit["programas"]:
                assert "codigo" not in program
                assert "descripcion" not in program
                assert program["tema"].strip()
                ids.append(program["id"])
                count += 1
        assert count == subject["total"]
    assert len(ids) == 84
    assert len(set(ids)) == 84


@pytest.mark.asyncio
async def test_units_are_listed_in_natural_order(client: AsyncClient):
    headers = await _headers(client)
    subjects = (await client.get(CATALOG, headers=headers)).json()
    romans = {"I": 1, "II": 2, "III": 3, "IV": 4}
    for subject in subjects:
        numbers = [romans[unit["unidad"].split("_")[1]] for unit in subject["unidades"]]
        assert numbers == sorted(numbers), subject["materia"]


@pytest.mark.asyncio
async def test_get_entry_returns_code_and_language(client: AsyncClient):
    headers = await _headers(client)
    cpp_id = await _find_id(client, headers, CPP_FILE)
    c_id = await _find_id(client, headers, C_FILE)

    cpp = await client.get(f"{CATALOG}{cpp_id}", headers=headers)
    assert cpp.status_code == 200, cpp.text
    body = cpp.json()
    assert body["lenguaje"] == "cpp"
    assert body["codigo"].strip()
    assert body["titulo"] == "Arbol binario inorden iterativo"
    assert body["materia_nombre"] and body["unidad_nombre"]
    assert body["descripcion"].strip() and body["tema"].strip()

    c = await client.get(f"{CATALOG}{c_id}", headers=headers)
    assert c.status_code == 200
    assert c.json()["lenguaje"] == "c"
    assert c.json()["titulo"] == "Arbol binario recorridos recursivo"


@pytest.mark.asyncio
async def test_unknown_entry_is_404(client: AsyncClient):
    headers = await _headers(client)
    res = await client.get(f"{CATALOG}no--existe", headers=headers)
    assert res.status_code == 404
    res = await client.post(f"{CATALOG}no--existe/use", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_catalog_requires_auth(client: AsyncClient):
    assert (await client.get(CATALOG)).status_code == 401
    assert (await client.get(f"{CATALOG}x--y")).status_code == 401
    assert (await client.post(f"{CATALOG}x--y/use")).status_code == 401


@pytest.mark.asyncio
async def test_use_creates_problem_and_reference(client: AsyncClient, vector_store):
    headers = await _headers(client)
    cpp_id = await _find_id(client, headers, CPP_FILE)

    res = await client.post(f"{CATALOG}{cpp_id}/use", headers=headers)
    assert res.status_code == 200, res.text
    problem = res.json()
    assert problem["titulo"] == "Arbol binario inorden iterativo"
    assert problem["lenguaje"] == "cpp"

    listed = (await client.get("/api/v1/problems/", headers=headers)).json()
    assert [p["id"] for p in listed] == [problem["id"]]

    assert len(vector_store.store) == 1
    metadata = next(iter(vector_store.store.values()))["metadata"]
    assert metadata["problema_id"] == problem["id"]
    assert metadata["tipo"] == "REFERENCIA"
    assert metadata["lenguaje"] == "cpp"
    assert metadata["autor"] == "Catálogo ESCOM"


@pytest.mark.asyncio
async def test_use_builds_statement_from_description(client: AsyncClient):
    headers = await _headers(client)
    entry_id = await _find_id(client, headers, C_FILE)
    detail = (await client.get(f"{CATALOG}{entry_id}", headers=headers)).json()

    problem = (await client.post(f"{CATALOG}{entry_id}/use", headers=headers)).json()
    assert problem["enunciado"] == detail["descripcion"]


@pytest.mark.asyncio
async def test_problems_list_exposes_catalog_id_only_for_adopted(client: AsyncClient):
    headers = await _headers(client)
    entry_id = await _find_id(client, headers, C_FILE)
    await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    created = await client.post(
        "/api/v1/problems/",
        headers=headers,
        json={"titulo": "Normal", "enunciado": "Un problema normal", "lenguaje": "c"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["catalogo_id"] is None

    listed = (await client.get("/api/v1/problems/", headers=headers)).json()
    by_title = {p["titulo"]: p for p in listed}
    assert by_title["Arbol binario recorridos recursivo"]["catalogo_id"] == entry_id
    assert by_title["Normal"]["catalogo_id"] is None


@pytest.mark.asyncio
async def test_use_is_idempotent_per_teacher(client: AsyncClient, vector_store):
    headers = await _headers(client)
    entry_id = await _find_id(client, headers, C_FILE)

    first = await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    second = await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    listed = (await client.get("/api/v1/problems/", headers=headers)).json()
    assert len(listed) == 1
    assert len(vector_store.store) == 1


@pytest.mark.asyncio
async def test_use_by_second_teacher_creates_separate_problem(client: AsyncClient, vector_store):
    first_headers = await _headers(client, "uno@escom.ipn.mx")
    second_headers = await _headers(client, "dos@escom.ipn.mx")
    entry_id = await _find_id(client, first_headers, C_FILE)

    first = await client.post(f"{CATALOG}{entry_id}/use", headers=first_headers)
    second = await client.post(f"{CATALOG}{entry_id}/use", headers=second_headers)
    assert first.json()["id"] != second.json()["id"]
    assert len(vector_store.store) == 2


@pytest.mark.asyncio
async def test_use_failure_leaves_no_problem_behind(client: AsyncClient, vector_store):
    headers = await _headers(client)
    entry_id = await _find_id(client, headers, C_FILE)

    vector_store.fail = True
    res = await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    assert res.status_code == 503, res.text
    assert (await client.get("/api/v1/problems/", headers=headers)).json() == []

    vector_store.fail = False
    retry = await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    assert retry.status_code == 200, retry.text
    assert len((await client.get("/api/v1/problems/", headers=headers)).json()) == 1
