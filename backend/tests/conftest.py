import os
import sys
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Agregar backend al sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app
from app.infrastructure.database.session import Base, get_db
from app.infrastructure.database.models import *  # ensure all models registered
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.infrastructure.vector_store import get_vector_store
from app.domain.ports.vector_store_port import VectorStorePort


# Mock Vector Store en memoria para tests aislados
class InMemoryVectorStore(VectorStorePort):
    def __init__(self):
        self.store = {}

    async def upsert_reference(self, reference_id: str, embedding: list, metadata: dict, document=None):
        self.store[reference_id] = {
            "embedding": embedding,
            "metadata": metadata,
            "document": document,
        }
        return True

    async def query_nearest(self, embedding: list, problema_id: int, top_k: int = 1):
        results = []
        for ref_id, data in self.store.items():
            if data["metadata"].get("problema_id") == problema_id:
                # Simular similitud alta si coincide
                results.append({
                    "reference_id": ref_id,
                    "similarity": 0.92,
                    "distance": 0.08,
                    "metadata": data["metadata"],
                })
        return results[:top_k]

    async def delete_reference(self, reference_id: str):
        self.store.pop(reference_id, None)
        return True


test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
test_vector_store = InMemoryVectorStore()
test_inference_engine = StubInferenceEngine()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_maker() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    def override_inference():
        return test_inference_engine

    def override_vector_store():
        return test_vector_store

    import app.infrastructure.database.session as db_session_module
    orig_maker = db_session_module.async_session_maker
    db_session_module.async_session_maker = test_session_maker

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_inference_engine] = override_inference
    app.dependency_overrides[get_vector_store] = override_vector_store

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()
    db_session_module.async_session_maker = orig_maker
