import app
from app.cli import app as cli_app


def test_app_imports() -> None:
    assert app is not None
    assert cli_app is not None
