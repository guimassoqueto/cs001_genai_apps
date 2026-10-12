import pytest

from genai_app import create_app
from genai_app.config import Config


def test_index_renders_model_name(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "claude-sonnet-5-5" in html
    assert "/static/js/app.js" in html


def test_unknown_page_is_html_not_json(client):
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.mimetype == "text/html"


def test_missing_api_key_fails_at_startup(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        create_app(Config())
