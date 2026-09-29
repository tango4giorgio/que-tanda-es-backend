import argparse
import json
import logging
import sys

from src.handlers.get_previews import lambda_handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke the previews Lambda locally")
    parser.add_argument("track_id", nargs="+")
    args = parser.parse_args()
    result = lambda_handler(
        {
            "version": "2.0",
            "routeKey": "POST /previews",
            "rawPath": "/previews",
            "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"trackIds": args.track_id}),
            "isBase64Encoded": False,
            "requestContext": {
                "stage": "$default",
                "http": {"method": "POST", "path": "/previews"},
            },
        },
        None,
    )
    for handler in logging.getLogger("tango-music-game-previews").handlers:
        handler.setStream(sys.stderr)
    print(json.dumps(json.loads(result["body"]), indent=2))
    return 0 if result["statusCode"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
