import argparse
import json
import statistics
import time
from unittest.mock import MagicMock

from src.models.routing import RoutingConfig
from src.services.gateway_service import GatewayService


def _stub_client() -> MagicMock:
    client = MagicMock()
    target_response = {"statusCode": 200, "headers": {}, "body": "{}"}

    def invoke(FunctionName: str, InvocationType: str, Payload: bytes) -> dict:
        return {"Payload": MagicMock(read=lambda: json.dumps(target_response).encode("utf-8"))}

    client.invoke.side_effect = invoke
    return client


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the gateway's own added processing overhead (SC-002)"
    )
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=50)
    args = parser.parse_args()

    config = RoutingConfig(
        entries=[
            {
                "method": "GET",
                "path": "/game",
                "target_function_name": "tango-music-game-get-game",
            }
        ]
    )
    service = GatewayService(config, lambda_client=_stub_client())

    from src.models.routing import ForwardedRequest

    forwarded = ForwardedRequest(method="GET", path="/game")

    for _ in range(args.warmup):
        service.invoke_target(config.entries[0], forwarded)

    durations_ms = []
    for _ in range(args.iterations):
        started = time.perf_counter()
        service.invoke_target(config.entries[0], forwarded)
        durations_ms.append((time.perf_counter() - started) * 1_000)

    durations_ms.sort()
    p95_index = min(int(len(durations_ms) * 0.95), len(durations_ms) - 1)
    print(
        json.dumps(
            {
                "iterations": args.iterations,
                "median_ms": round(statistics.median(durations_ms), 4),
                "p95_ms": round(durations_ms[p95_index], 4),
                "max_ms": round(max(durations_ms), 4),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
