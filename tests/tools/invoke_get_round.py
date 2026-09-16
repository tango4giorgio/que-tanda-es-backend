import argparse
import json
import logging
import sys

from src.handlers.get_round import lambda_handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke the round Lambda locally")
    parser.add_argument("--exclude-artist", action="append", default=[])
    args = parser.parse_args()
    query = "&".join(f"excludeArtist={value}" for value in args.exclude_artist)
    result = lambda_handler(
        {
            "version": "2.0",
            "routeKey": "GET /round",
            "rawPath": "/round",
            "rawQueryString": query,
            "queryStringParameters": (
                {"excludeArtist": args.exclude_artist[-1]} if args.exclude_artist else None
            ),
            "multiValueQueryStringParameters": (
                {"excludeArtist": args.exclude_artist} if args.exclude_artist else {}
            ),
            "requestContext": {
                "stage": "$default",
                "http": {"method": "GET", "path": "/round"},
            },
        },
        None,
    )
    for handler in logging.getLogger("tango-music-game-round").handlers:
        handler.setStream(sys.stderr)
    print(json.dumps(json.loads(result["body"]), indent=2))
    return 0 if result["statusCode"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
