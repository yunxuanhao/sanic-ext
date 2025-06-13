import asyncio
import os
import shutil
import subprocess
import time

from typing import Any

import httpx
import prometheus_client
import pytest

from sanic import Request, Sanic
from sanic.log import logger
from sanic.response import text

from sanic_ext import Extend


counter = prometheus_client.Counter(
    "event_counter", "Track the number of events", ["counter_name", "label"]
)

def get_metrics(app: Sanic) -> dict[str, Any]:
    test_client = app.test_client
    _, response = test_client.get("/metrics")
    assert response.status == 200
    logger.info(f"Metrics response: {response.text}")
    return response.text

def call_path(app: Sanic, path: str, method: str = "get"):
    test_client = app.test_client
    _, response = test_client.get(path)
    assert response.status == 200

def counter_app_multiproc():
    """ Create a Sanic app with Prometheus metrics for multiprocess testing """
    app = Sanic("counter_app_multiproc")
    Extend(app)

    @app.get("/test1")
    async def handler1(request: Request):
        counter.labels("test1", "label1").inc(1)
        # Simulate some processing time
        # make sure all workers handle the request
        time.sleep(0.1)
        return text("ok")

    return app


@pytest.fixture(scope="module")
def start_server():
    metrics_dir = "/tmp/sanic_ext_prometheus_multiproc_dir"
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = metrics_dir
    if os.path.exists(metrics_dir):
        shutil.rmtree(metrics_dir)
    os.makedirs(metrics_dir)

    process = subprocess.Popen(
        [
            "python",
            "-m",
            "sanic",
            "tests.extensions.prometheus.test_metrics:counter_app_multiproc",
            "--workers=4",
            "--host=0.0.0.0",
            "--port=9371"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(2)
    yield process

    process.terminate()
    process.wait()

def test_single_process_metrics(app: Sanic):
    """ test single process metrics """

    @app.get("/test1")
    async def handler1(request: Request):
        counter.labels("test1", "label1").inc(1)
        return text("ok")

    call_count = 20
    for _ in range(call_count):
        call_path(app, "/test1")

    res = get_metrics(app)
    except_metrics = (
        'event_counter_total{counter_name="test1",label="label1"} '
        + str(call_count) + '.0'
    )
    assert except_metrics in res.splitlines()

@pytest.mark.asyncio
async def test_multiprocess_metrics(start_server):
    call_count = 300
    semaphore = asyncio.Semaphore(40)

    async def fetch_url(url: str):
        async with semaphore:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                assert response.status_code == 200

    tasks = [fetch_url("http://0.0.0.0:9371/test1") for _ in range(call_count)]
    await asyncio.gather(*tasks)

    res = httpx.get("http://0.0.0.0:9371/metrics")
    except_metrics = (
        'event_counter_total{counter_name="test1",label="label1"} '
        + str(call_count) + '.0'
    )
    assert res.status_code == 200
    assert except_metrics in res.text.splitlines()
