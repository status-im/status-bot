import threading

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from status_bot.modules.base import BaseModule, ModuleType


class APIServerModule(BaseModule):

    @property
    def module_type(self) -> ModuleType:
        return ModuleType.SERVICE

    def on_start(self):
        api_config = self.ctx.shared_state["config"].api
        self._host = api_config.host
        self._port = api_config.port
        self._app: FastAPI = self.ctx.shared_state["fastapi_app"]
        self._server = None
        self._add_auth_middleware(api_config.api_key)

    def _add_auth_middleware(self, api_key: str):
        if not api_key:
            return

        exempt = {"/health", "/docs", "/redoc", "/openapi.json"}

        @self._app.middleware("http")
        async def require_api_key(request: Request, call_next):
            if request.url.path in exempt:
                return await call_next(request)
            if request.headers.get("X-API-Key") != api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
            return await call_next(request)

    def execute(self):
        if not self.ctx.shared_state["config"].api.enable:
            self.ctx.logger.info("API server is disabled, skipping startup")
            return

        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
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
