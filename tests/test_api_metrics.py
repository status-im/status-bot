import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from status_bot.modules.api_server import APIServerModule
from status_bot.modules.base import ModuleConfig, ModuleContext
from status_bot.modules.messaging import MessagingModule

REQUESTS = "status_bot_api_requests_total"
DURATION_COUNT = "status_bot_api_request_duration_seconds_count"
AUTH_FAILURES = "status_bot_api_auth_failures_total"


class StubAccount:
    def __init__(self):
        self.contacts = []
        self.chats = []
        self.communities = []

    def get_messages(self, chat_id, start=None, end=None):
        return []


def _build_api(api_key=None, register_metrics=True, with_error_route=False):
    """Build a FastAPI app with the api_server middleware and messaging routes."""
    app = FastAPI(title="Status Bot API")
    account = StubAccount()
    config = SimpleNamespace(
        api=SimpleNamespace(host="127.0.0.1", port=8081, api_key=api_key, enable=True)
    )
    shared_state = {"config": config, "fastapi_app": app}

    api_module = APIServerModule(
        ModuleContext(
            account=account,
            config=ModuleConfig(name="api_server", settings={}),
            shared_state=shared_state,
            stop_event=threading.Event(),
        )
    )
    registry = CollectorRegistry()
    if register_metrics:
        api_module.register_metrics(registry=registry)

    messaging_module = MessagingModule(
        ModuleContext(
            account=account,
            config=ModuleConfig(name="messaging", settings={}),
            shared_state=shared_state,
            stop_event=threading.Event(),
        )
    )

    # Order matters: register_metrics() before on_start(), auth middleware
    # before metrics middleware (so 401 responses are recorded).
    api_module.on_start()
    messaging_module.on_start()

    if with_error_route:

        @app.get("/boom")
        def boom():
            raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    return SimpleNamespace(client=client, registry=registry, api_module=api_module)


def _labels(**overrides):
    labels = {"module": "api_server", "method": "GET", "path": "/health", "status": "200"}
    labels.update(overrides)
    return labels


def _duration_labels(**overrides):
    labels = {"module": "api_server", "method": "GET", "path": "/health"}
    labels.update(overrides)
    return labels


def test_successful_request_is_counted_and_timed():
    env = _build_api()

    response = env.client.get("/health")

    assert response.status_code == 200
    assert env.registry.get_sample_value(REQUESTS, _labels()) == 1
    assert env.registry.get_sample_value(DURATION_COUNT, _duration_labels()) == 1


def test_path_label_uses_route_template_not_raw_path():
    env = _build_api()

    response = env.client.get("/api/v1/chats/chat-42/messages")

    assert response.status_code == 200
    template = "/api/v1/chats/{chat_id}/messages"
    assert env.registry.get_sample_value(REQUESTS, _labels(path=template)) == 1
    # The concrete chat id must never appear as a label value.
    raw_path = "/api/v1/chats/chat-42/messages"
    assert env.registry.get_sample_value(REQUESTS, _labels(path=raw_path)) is None


def test_unknown_path_is_labeled_unmatched():
    env = _build_api()

    response = env.client.get("/does-not-exist")

    assert response.status_code == 404
    assert env.registry.get_sample_value(REQUESTS, _labels(path="unmatched", status="404")) == 1


def test_auth_failure_is_counted_and_recorded_as_401():
    env = _build_api(api_key="secret")

    denied = env.client.get("/api/v1/contacts")

    assert denied.status_code == 401
    assert env.registry.get_sample_value(AUTH_FAILURES, {"module": "api_server"}) == 1
    # The metrics middleware wraps the auth middleware, so the 401 is recorded
    # (routing never happened, hence 'unmatched').
    assert env.registry.get_sample_value(REQUESTS, _labels(path="unmatched", status="401")) == 1

    allowed = env.client.get("/api/v1/contacts", headers={"X-API-Key": "secret"})

    assert allowed.status_code == 200
    assert env.registry.get_sample_value(AUTH_FAILURES, {"module": "api_server"}) == 1
    assert env.registry.get_sample_value(REQUESTS, _labels(path="/api/v1/contacts")) == 1


def test_unhandled_exception_is_recorded_as_500():
    env = _build_api(with_error_route=True)

    response = env.client.get("/boom")

    assert response.status_code == 500
    assert env.registry.get_sample_value(REQUESTS, _labels(path="/boom", status="500")) == 1


def test_metrics_disabled_is_a_safe_noop():
    env = _build_api(api_key="secret", register_metrics=False)

    assert env.api_module._requests_total is None
    assert env.api_module._auth_failures is None

    # Both middlewares are registered but must not touch any metric.
    assert env.client.get("/health").status_code == 200
    assert env.client.get("/api/v1/contacts").status_code == 401
