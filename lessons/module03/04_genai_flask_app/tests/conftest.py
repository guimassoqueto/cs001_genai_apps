import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from genai_app import create_app
from genai_app.config import TestingConfig


@pytest.fixture
def replies():
    """Canned model replies, one per model call. Tests append to it before calling the API."""
    return []


@pytest.fixture
def app(replies):
    # A list iterator sees items appended after it was created, so tests can fill `replies` later.
    return create_app(TestingConfig(), chat_model=GenericFakeChatModel(messages=iter(replies)))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def valid_analysis():
    return {
        "summary": "Customer was charged twice for the same order.",
        "sentiment": 20,
        "category": "billing",
        "action": "Refund the duplicate charge and confirm by email.",
    }


@pytest.fixture
def valid_reply(valid_analysis):
    return json.dumps(valid_analysis)
