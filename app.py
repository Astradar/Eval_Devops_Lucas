import os
import time

import redis
from flask import Flask, request, Response
from prometheus_client import Counter, Histogram, Gauge
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379)

REQUESTS = Counter(
    "http_requests_total", "Nombre de requetes", ["endpoint", "code"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "Duree des requetes", ["endpoint"]
)
VERSION = Gauge("app_version_info", "Version deployee", ["version"])
VERSION.labels(os.getenv("APP_VERSION", "dev")).set(1)


@app.before_request
def start_timer():
    request.start = time.time()


@app.after_request
def record_metrics(response):
    LATENCY.labels(request.path).observe(time.time() - request.start)
    REQUESTS.labels(request.path, response.status_code).inc()
    return response


@app.route("/")
def home():
    visites = r.incr("visites")
    return f"Nombre de visites : {visites}"


@app.route("/health")
def health():
    try:
        r.ping()
        return "ok"
    except redis.exceptions.ConnectionError:
        return "redis down", 500


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
