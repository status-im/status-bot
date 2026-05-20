import logging

from bot.config import PrometheusConfig
from bot.modules.manager import ModuleManager
from prometheus_client import start_http_server, Gauge, Counter



def start_prometheus(prometheus_config: PrometheusConfig, manager: ModuleManager, logger: logging.Logger):
    if not prometheus_config.enabled:
        logger.info("Prometheus metrics disabled")
        return

    try:
        health = Gauge("status_bot_health", "Bot health status")
        version = Gauge("status_bot_version", "Bot version", ["version"])
        module_loaded = Gauge(
            "status_bot_module_loaded", "Module loaded", ["module"]
        )
        module_errors = Counter(
            "status_bot_module_errors_total", "Module errors", ["module"]
        )
        module_restarts = Counter(
            "status_bot_module_restarts_total", "Module restarts", ["module"]
        )

        health.set(1)
        version.labels(version="0.1.0").set(1)

        for module_name in manager.module_names:
            module_loaded.labels(module=module_name).set(1)

        host = prometheus_config.host
        port = prometheus_config.port
        start_http_server(port, host)
        logger.info(f"Prometheus metrics server started on {host}:{port}")
    except ImportError:
        logger.warning(
            "prometheus-client not installed. Install with: pip install prometheus-client"
        )
