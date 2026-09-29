import argparse
import json
import logging
import sys

import src.handlers.gateway as gateway_module
from src.handlers.get_game import lambda_handler as get_game_handler
from src.handlers.get_previews import lambda_handler as get_previews_handler
from src.models.routing import RoutingConfig
from src.services.gateway_service import GatewayService

# Maps target function names to their in-process handler, so this harness can
# exercise the full gateway request/response translation without any live AWS
# Lambda invocation.
_LOCAL_TARGETS = {
    "tango-music-game-get-game": get_game_handler,
    "tango-music-game-get-previews": get_previews_handler,
}


class _PayloadResult:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class LocalLambdaClient:
    """Substitutes an in-process handler call for boto3's Lambda invoke()."""

    def invoke(self, FunctionName: str, InvocationType: str, Payload: bytes) -> dict:
        handler = _LOCAL_TARGETS.get(FunctionName)
        if handler is None:
            return {"FunctionError": "Unhandled", "Payload": _PayloadResult(b"{}")}
        event = json.loads(Payload)
        result = handler(event, None)
        return {"Payload": _PayloadResult(json.dumps(result).encode("utf-8"))}


def _local_routing_config() -> RoutingConfig:
    return RoutingConfig(
        entries=[
            {
                "method": "GET",
                "path": "/game",
                "target_function_name": "tango-music-game-get-game",
            },
            {
                "method": "POST",
                "path": "/previews",
                "target_function_name": "tango-music-game-get-previews",
            }
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke the gateway Lambda locally")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--path", default="/game")
    parser.add_argument("--body", default=None)
    args = parser.parse_args()

    gateway_module._gateway_service = GatewayService(
        _local_routing_config(), lambda_client=LocalLambdaClient()
    )
    gateway_module._cold_start_error = None

    for handler in logging.getLogger("tango-music-game-gateway").handlers:
        handler.setStream(sys.stderr)

    result = gateway_module.lambda_handler(
        {
            "version": "2.0",
            "routeKey": f"{args.method} {args.path}",
            "rawPath": args.path,
            "rawQueryString": "",
            "headers": {},
            "body": args.body,
            "isBase64Encoded": False,
            "requestContext": {"http": {"method": args.method, "path": args.path}},
        },
        None,
    )
    print(json.dumps(json.loads(result["body"]), indent=2))
    return 0 if result["statusCode"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
