import importlib

from sanic.exceptions import SanicException

from ..base import Extension
from .metrics import Metrics


class PrometheusExtension(Extension):
    name = "prometheus"
    MIN_VERSION = (22, 9)

    def startup(self, bootstrap) -> None:
        if self.included():
            if self.MIN_VERSION > bootstrap.sanic_version:
                min_version = ".".join(map(str, self.MIN_VERSION))
                sanic_version = ".".join(map(str, bootstrap.sanic_version))
                raise SanicException(
                    f"The prometheus extension only works with Sanic "
                    f"v{min_version} and above. It looks like you are "
                    f"running {sanic_version}."
                )

            # 检查 prometheus_client 是否安装
            spec = importlib.util.find_spec("prometheus_client")
            prometheus_available = spec is not None
            if not prometheus_available:
                raise SanicException(
                    (
                        "The prometheus extension requires the "
                        "'prometheus_client' library to be installed."
                    )
                )
            Metrics.setup(self.app)

    def included(self):
        return self.config.PROMETHEUS
