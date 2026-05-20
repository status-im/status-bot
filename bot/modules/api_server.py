import threading

import uvicorn
from fastapi import FastAPI

from bot.modules.base import BaseModule, ModuleType


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
