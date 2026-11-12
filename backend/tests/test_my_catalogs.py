import pytest
from httpx import AsyncClient

MINE = "/api/v1/my-catalogs/"
CATALOG = "/api/v1/catalog/"
CODE = "int main(void) { return 0; }\n"


async def _headers(client: AsyncClient, email: str = "propio@escom.ipn.mx") -> dict:
    payload = {"email": email, "password": "PasswordSegura123!", "nombre": "Prof. Propio"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": payload["password"]})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _catalog(client: AsyncClient, headers: dict, nombre: str = "Mis problemas") -> dict:
    res = await client.post(MINE, headers=headers, json={"nombre": nombre})
    assert res.status_code == 201, res.text
    return res.json()


async def _program(client: AsyncClient, headers: dict, catalog_id: int, **extra) -> dict:
    body = {"titulo": "Suma", "enunciado": "Suma dos enteros", "lenguaje": "c", "codigo": CODE, **extra}
    res = await client.post(f"{MINE}{catalog_id}/programs", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_create_catalog_add_program_and_list(client: AsyncClient):
    headers = await _headers(client)
    catalog = await _catalog(client, headers)
    program = await _program(client, headers, catalog["id"])
    assert program["id"].startswith("mio-")

    listed = (await client.get(MINE, headers=headers)).json()
    assert [(c["nombre"], [p["titulo"] for p in c["programas"]]) for c in listed] == [("Mis problemas", ["Suma"])]
    assert "codigo" not in listed[0]["programas"][0]


@pytest.mark.asyncio
async def test_rejects_blank_name_and_empty_code(client: AsyncClient):
    headers = await _headers(client)
    assert (await client.post(MINE, headers=headers, json={"nombre": "   "})).status_code == 422
    catalog = await _catalog(client, headers)
    res = await client.post(
        f"{MINE}{catalog['id']}/programs", headers=headers, json={"titulo": "X", "codigo": ""}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_catalogs_are_private_to_their_owner(client: AsyncClient):
    owner = await _headers(client)
    other = await _headers(client, "otro@escom.ipn.mx")
    catalog = await _catalog(client, owner)
    program = await _program(client, owner, catalog["id"])

    assert (await client.get(MINE, headers=other)).json() == []
    assert (await client.post(f"{MINE}{catalog['id']}/programs", headers=other,
                              json={"titulo": "X", "codigo": CODE})).status_code == 404
    assert (await client.delete(f"{MINE}{catalog['id']}", headers=other)).status_code == 404
    assert (await client.get(f"{CATALOG}{program['id']}", headers=other)).status_code == 404
    assert (await client.post(f"{CATALOG}{program['id']}/use", headers=other)).status_code == 404
    assert (await client.delete(f"{MINE}programs/{program['id'][4:]}", headers=other)).status_code == 404


@pytest.mark.asyncio
async def test_own_program_detail_and_use(client: AsyncClient, vector_store):
    headers = await _headers(client)
    catalog = await _catalog(client, headers)
    program = await _program(client, headers, catalog["id"], lenguaje="cpp")

    detail = (await client.get(f"{CATALOG}{program['id']}", headers=headers)).json()
    assert detail["codigo"] == CODE and detail["descripcion"] == "Suma dos enteros"
    assert detail["materia_nombre"] == "Mis problemas"

    problem = (await client.post(f"{CATALOG}{program['id']}/use", headers=headers)).json()
    assert problem["catalogo_id"] == program["id"] and problem["lenguaje"] == "cpp"
    again = (await client.post(f"{CATALOG}{program['id']}/use", headers=headers)).json()
    assert again["id"] == problem["id"]
    assert next(iter(vector_store.store.values()))["metadata"]["autor"] == "Catálogo propio"


@pytest.mark.asyncio
async def test_save_library_problem_copies_it_and_survives_deletion(client: AsyncClient):
    headers = await _headers(client)
    catalog = await _catalog(client, headers)
    problem = (await client.post(
        "/api/v1/problems/", headers=headers, json={"titulo": "Factorial", "enunciado": "n!", "lenguaje": "c"}
    )).json()

    no_ref = await client.post(f"{MINE}{catalog['id']}/programs/from-problem/{problem['id']}", headers=headers)
    assert no_ref.status_code == 422

    ref = await client.post(
        f"/api/v1/problems/{problem['id']}/references",
        headers=headers,
        params={"autor": "Docente", "contenido": CODE},
    )
    assert ref.status_code == 201, ref.text
    saved = await client.post(f"{MINE}{catalog['id']}/programs/from-problem/{problem['id']}", headers=headers)
    assert saved.status_code == 201, saved.text

    assert (await client.delete(f"/api/v1/problems/{problem['id']}", headers=headers)).status_code == 204
    detail = (await client.get(f"{CATALOG}{saved.json()['id']}", headers=headers)).json()
    assert detail["codigo"] == CODE and detail["descripcion"] == "n!" and detail["titulo"] == "Factorial"


@pytest.mark.asyncio
async def test_ai_variants_are_copied_and_restored_without_calling_the_llm(client: AsyncClient, vector_store):
    from app.domain.errors import GenerationError
    from app.domain.ports.reference_generator_port import ReferenceGeneratorPort
    from app.infrastructure.llm import get_reference_generator
    from app.main import app

    class Generator(ReferenceGeneratorPort):
        calls = 0

        async def generate(self, *, enunciado, reference_code, instructions, language):
            Generator.calls += 1
            return "int dup(int n) { return n + n; }\nint main(void) { return dup(1); }\n"

    app.dependency_overrides[get_reference_generator] = lambda: Generator()
    headers = await _headers(client)
    catalog = await _catalog(client, headers)
    problem = (await client.post(
        "/api/v1/problems/", headers=headers, json={"titulo": "Doble", "enunciado": "2n", "lenguaje": "c"}
    )).json()
    pid = problem["id"]
    await client.post(f"/api/v1/problems/{pid}/references", headers=headers, params={"autor": "D", "contenido": CODE})
    variant = await client.post(
        f"/api/v1/problems/{pid}/variants", headers=headers, json={"titulo": "Con funcion", "instrucciones": "usa funcion"}
    )
    assert variant.status_code == 201, variant.text
    saved = (await client.post(f"{MINE}{catalog['id']}/programs/from-problem/{pid}", headers=headers)).json()

    # The original is gone; the catalog still holds the variant.
    assert (await client.delete(f"/api/v1/problems/{pid}", headers=headers)).status_code == 204
    assert vector_store.store == {}
    calls_before = Generator.calls

    adopted = (await client.post(f"{CATALOG}{saved['id']}/use", headers=headers)).json()
    assert Generator.calls == calls_before
    tipos = sorted(v["metadata"]["tipo"] for v in vector_store.store.values())
    assert tipos == ["REFERENCIA", "VARIANTE"]
    variant_meta = next(v["metadata"] for v in vector_store.store.values() if v["metadata"]["tipo"] == "VARIANTE")
    assert variant_meta["variante_problema_id"] == adopted["id"] and variant_meta["titulo"] == "Con funcion"

    # Deleting the program removes its saved variants too.
    assert (await client.delete(f"{MINE}programs/{saved['id'][4:]}", headers=headers)).status_code == 204


@pytest.mark.asyncio
async def test_other_teachers_problem_cannot_be_saved(client: AsyncClient):
    owner = await _headers(client)
    other = await _headers(client, "otro@escom.ipn.mx")
    problem = (await client.post(
        "/api/v1/problems/", headers=owner, json={"titulo": "P", "enunciado": "e", "lenguaje": "c"}
    )).json()
    catalog = await _catalog(client, other)
    res = await client.post(f"{MINE}{catalog['id']}/programs/from-problem/{problem['id']}", headers=other)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_program_and_catalog(client: AsyncClient):
    headers = await _headers(client)
    catalog = await _catalog(client, headers)
    program = await _program(client, headers, catalog["id"])

    assert (await client.delete(f"{MINE}programs/{program['id'][4:]}", headers=headers)).status_code == 204
    assert (await client.get(MINE, headers=headers)).json()[0]["programas"] == []

    second = await _program(client, headers, catalog["id"])
    assert (await client.delete(f"{MINE}{catalog['id']}", headers=headers)).status_code == 204
    assert (await client.get(MINE, headers=headers)).json() == []
    assert (await client.get(f"{CATALOG}{second['id']}", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_requires_auth(client: AsyncClient):
    assert (await client.get(MINE)).status_code == 401
