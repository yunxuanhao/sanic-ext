import os


# try to import the prometheus multiprocess module
try:
    import prometheus_client as prometheus

    from prometheus_client import CollectorRegistry, core, multiprocess
    from prometheus_client.exposition import generate_latest
except ImportError:
    prometheus = None

from prometheus_client import CollectorRegistry, core, multiprocess
from prometheus_client.exposition import generate_latest
from sanic import Sanic, response
from sanic.log import logger

from ..openapi.openapi import exclude


def get_prometheus_multiproc_dir() -> str:
    prome_stats = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if not prome_stats:
        prome_stats = os.getenv("prometheus_multiproc_dir")
    return prome_stats


class Metrics:
    REGISTRY = core.REGISTRY if prometheus else None

    @classmethod
    def setup(cls, app: Sanic):
        if prometheus:
            # check if multiprocess mode is enabled
            # https://prometheus.github.io/client_python/multiprocess/
            if get_prometheus_multiproc_dir():
                logger.info("Using multiprocess mode for Prometheus metrics")
                cls.REGISTRY = CollectorRegistry()
                multiprocess.MultiProcessCollector(cls.REGISTRY)

                # Register the cleanup listener to mark the process as dead
                @app.listener("after_server_stop")
                def after_server_stop(app, loop):
                    logger.info(f"Marking process as dead, PID: {os.getpid()}")
                    multiprocess.mark_process_dead(os.getpid())

            @app.get(app.config.PROMETHEUS_URI_TO_METRICS)
            @exclude(True)
            async def metrics(request):
                output = generate_latest(cls.REGISTRY).decode("utf-8")
                content_type = prometheus.exposition.CONTENT_TYPE_LATEST
                return response.text(body=output, content_type=content_type)
        else:
            logger.warning(
                "Prometheus metrics are not available. "
                "Please install the 'prometheus_client' library."
            )
