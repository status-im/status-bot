import logging

from status_bot.config import MetricsConfig
from status_bot.modules.manager import ModuleManager
from prometheus_client import start_http_server, Gauge

logger = logging.getLogger(__name__)


def start_prometheus(metrics_config: MetricsConfig, manager: ModuleManager, account_name: str):
    if not metrics_config.enabled:
        logger.info("Prometheus metrics exporter disabled")
        return

    health = Gauge("status_bot_health", "Bot health status")
    version = Gauge("status_bot_version", "Bot version", ["version", "name"])

    module_loaded = Gauge(
        "status_bot_module_loaded", "Module loaded", ["module"]
    )

    health.set(1)
    version.labels(version="1.0.0", name=account_name).set(1)

    for module_name in manager.module_names:
        module_loaded.labels(module=module_name).set(1)

    for module_name in manager.module_names:
        module = manager.modules[module_name]
        module.register_metrics()

    host = metrics_config.host
    port = metrics_config.port
    start_http_server(port, host)
    logger.info(f"Prometheus metrics exporter server started on {host}:{port}")
