import pytest


@pytest.fixture(autouse=True)
def bypass_pin(request, monkeypatch):
    """Libera a trava de PIN nos testes, exceto nos marcados com @pytest.mark.real_pin."""
    if "real_pin" in request.keywords:
        return
    import app.auth as auth

    monkeypatch.setattr(auth, "token_valid", lambda token=None: True)


def pytest_configure(config):
    config.addinivalue_line("markers", "real_pin: mantém a trava de PIN ativa no teste")
