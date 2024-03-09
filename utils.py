from urllib import parse
from uuid import uuid4

from fastapi.responses import RedirectResponse


def encode_query_params(params: dict) -> str:
    return parse.urlencode(params)


def redirect_with_query_params(
    url: str, params: dict, status_code=302
) -> RedirectResponse:
    query_params = encode_query_params(params)
    # return redirect response
    return RedirectResponse(url=f"{url}?{query_params}", status_code=status_code)


def redirect_with_error(url: str, error: str, status_code=302) -> RedirectResponse:
    return redirect_with_query_params(url, {"error": error}, status_code)


def generate_uuid() -> str:
    return str(uuid4())
