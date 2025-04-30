import json

from flask import Request, Response


def handle(request: Request) -> Response:
    print(request.path)
    print(request.data)
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    print("Request data:")
    print(json.dumps(data_dict, indent=2))
    return Response("OK", status=200)
