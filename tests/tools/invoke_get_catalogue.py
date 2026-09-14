import json

from src.handlers.get_catalogue import lambda_handler

if __name__ == "__main__":
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
    print(json.dumps(result))
