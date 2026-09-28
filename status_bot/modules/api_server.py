import logging
import threading
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Histogram

from status_bot.modules.base import BaseModule, ModuleType

logger = logging.getLogger(__name__)

UVICORN_LOG_CONFIG = {
    "version": 1,
    "incremental": True,
    "loggers": {
        "uvicorn": {"propagate": True, "handlers": []},
        "uvicorn.error": {"propagate": True, "handlers": []},
        "uvicorn.access": {"propagate": True, "handlers": []},
    },
}


class APIServerModule(BaseModule):
    _requests_total: Counter | None = None
    _request_duration: Histogram | None = None
    _auth_failures: Counter | None = None
    _metrics_middleware_registered = False

    @property
    def module_type(self) -> set[ModuleType]:
        return {ModuleType.SERVICE}

    def on_start(self):
        api_config = self.ctx.shared_state["config"].api
        self._host = api_config.host
        self._port = api_config.port
        self._app: FastAPI = self.ctx.shared_state["fastapi_app"]
        self._server = None
        self._add_auth_middleware(api_config.api_key)
        self._add_metrics_middleware()

    def register_metrics(self, registry: CollectorRegistry = REGISTRY) -> None:
        self._requests_total = Counter(
            "status_bot_api_requests_total",
            "Total number of HTTP requests handled by the API server",
            ["module", "method", "path", "status"],
            registry=registry,
        )
        self._request_duration = Histogram(
            "status_bot_api_request_duration_seconds",
            "HTTP request duration of the API server",
            ["module", "method", "path"],
            registry=registry,
        )
        self._auth_failures = Counter(
            "status_bot_api_auth_failures_total",
            "Number of API requests rejected because of a missing or invalid API key",
            ["module"],
            registry=registry,
        )

    def _add_auth_middleware(self, api_key: str):
        if not api_key:
            return

        exempt = {"/health", "/docs", "/redoc", "/openapi.json"}

        @self._app.middleware("http")
        async def require_api_key(request: Request, call_next):
            if request.url.path in exempt:
                return await call_next(request)
            if request.headers.get("X-API-Key") != api_key:
                auth_failures = self._auth_failures
                if auth_failures is not None:
                    auth_failures.labels(module=self.name).inc()
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
            return await call_next(request)

    def _add_metrics_middleware(self) -> None:
        if self._metrics_middleware_registered:
            return
        self._metrics_middleware_registered = True

        @self._app.middleware("http")
        async def record_metrics(request: Request, call_next):
            start = time.perf_counter()
            try:
                response = await call_next(request)
            except Exception:
                # Record unhandled errors as 500, then let them propagate.
                self._record_request(request, "500", time.perf_counter() - start)
                raise
            self._record_request(request, str(response.status_code), time.perf_counter() - start)
            return response

    def _record_request(self, request: Request, status: str, duration: float) -> None:
        requests_total = self._requests_total
        request_duration = self._request_duration
        if requests_total is None or request_duration is None:
            return
        labels = {
            "module": self.name,
            "method": request.method,
            "path": self._route_path(request),
        }
        requests_total.labels(status=status, **labels).inc()
        request_duration.labels(**labels).observe(duration)

    @staticmethod
    def _route_path(request: Request) -> str:
        """Return the matched route template, or 'unmatched' for unrouted requests."""
        route = request.scope.get("route")
        path = getattr(route, "path", None)
        return path if path else "unmatched"

    def execute(self):
        if not self.ctx.shared_state["config"].api.enable:
            logger.info("API server is disabled, skipping startup")
            return

        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_config=UVICORN_LOG_CONFIG,
            log_level="info",
        )
        server = uvicorn.Server(config)
        self._server = server
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        self.ctx.stop_event.wait()
        server.should_exit = True
        thread.join(timeout=10)

    def on_stop(self):
        if self._server:
            self._server.should_exit = True

    def on_event(self, event_type: str, event: dict) -> None:
        pass
