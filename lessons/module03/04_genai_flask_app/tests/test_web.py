import pytest

from genai_app import create_app
from genai_app.config import Config


def test_index_renders_the_model_picker_and_ab_switch(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="abToggle"' in html
    assert '<option value="claude-sonnet-5-5" selected>Claude Sonnet 5.5</option>' in html
    assert html.count('name="abModels"') == 4
    assert "/static/js/app.js" in html


def test_unknown_page_is_html_not_json(client):
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.mimetype == "text/html"


def test_missing_api_key_fails_at_startup(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE", str(tmp_path / "db.sqlite3"))

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        create_app(Config())


def test_default_model_must_be_in_the_model_list(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODELS", "claude-haiku-5-5")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

    with pytest.raises(RuntimeError, match="ANTHROPIC_MODEL"):
        create_app(Config())
