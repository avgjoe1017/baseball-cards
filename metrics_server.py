import os
import time

from prometheus_client import Counter, Gauge, start_http_server


def parse_log_metrics(log_path):
    crawl_success = 0
    api_429s = 0
    queue_depth = 0  # Placeholder, update if you track a queue
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if "Finished collection attempt" in line:
                    crawl_success += 1
                if "429" in line or "rate-limited" in line:
                    api_429s += 1
                # Optionally parse queue depth if you log it
    except Exception:
        pass
    return crawl_success, api_429s, queue_depth


def main():
    # Prometheus metrics
    CRAWL_SUCCESS = Counter("crawl_success", "Number of successful crawl cycles")
    API_429S = Counter("api_429s", "Number of API 429/rate-limit events")
    QUEUE_DEPTH = Gauge("queue_depth", "Current queue depth")

    log_path = os.path.join(
        os.path.dirname(__file__), "sold_valuation_collector_log.txt"
    )
    last_crawl_success = 0
    last_api_429s = 0
    # Start HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server running on :8000/metrics")
    while True:
        crawl_success, api_429s, queue_depth = parse_log_metrics(log_path)
        # Increment counters only for new events
        if crawl_success > last_crawl_success:
            CRAWL_SUCCESS.inc(crawl_success - last_crawl_success)
            last_crawl_success = crawl_success
        if api_429s > last_api_429s:
            API_429S.inc(api_429s - last_api_429s)
            last_api_429s = api_429s
        QUEUE_DEPTH.set(queue_depth)
        time.sleep(15)


if __name__ == "__main__":
    main()
