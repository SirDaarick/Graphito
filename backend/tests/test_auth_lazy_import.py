import builtins
import importlib
import sys

import pytest
from fastapi import HTTPException


def _block_google(monkeypatch):
    """Make any `import google.*` raise ImportError, as if google-auth were absent."""
    for name in [m for m in sys.modules if m == "google" or m.startswith("google.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "google" or name.startswith("google."):
            raise ImportError(f"No module named {name!r} (blocked by test)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


@pytest.mark.asyncio
async def test_auth_service_imports_and_google_login_is_503_without_google_auth(monkeypatch):
    _block_google(monkeypatch)
    monkeypatch.delitem(sys.modules, "app.application.services.auth_service", raising=False)

    module = importlib.import_module("app.application.services.auth_service")

    service = module.AuthService(db=None)
    with pytest.raises(HTTPException) as exc:
        await service.login_with_google("dummy-token")
    assert exc.value.status_code == 503
