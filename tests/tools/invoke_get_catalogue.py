import json
import logging
import sys

from src.handlers.get_catalogue import lambda_handler

if __name__ == "__main__":
    for handler in logging.getLogger("recording-provider-registry").handlers:
        handler.setStream(sys.stderr)
    result = lambda_handler(
        {
            "version": "2.0",
            "routeKey": "GET /catalogue",
            "rawPath": "/catalogue",
            "requestContext": {
                "stage": "$default",
                "http": {"method": "GET", "path": "/catalogue"},
            },
        },
        None,
    )
    if result["statusCode"] != 200:
        raise SystemExit(json.dumps(result))
    payload = json.loads(result["body"])
    if not isinstance(payload.get("recordings"), list):
        raise SystemExit("Invalid registry response: recordings must be an array")
    print(json.dumps(payload, indent=2))
