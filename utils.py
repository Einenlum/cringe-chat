from urllib import parse
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import RedirectResponse


def encode_query_params(params: dict) -> str:
    return parse.urlencode(params)


def redirect_with_query_params(
    request: Request, url: str, params: dict, status_code=302
) -> Response:
    query_params = encode_query_params(params)
    url = f"{url}?{query_params}"

    if request.headers.get("HX-Request"):
        return Response(status_code=status_code, headers={"HX-Redirect": url})
    # return redirect response
    return RedirectResponse(
        # url=url, status_code=status_code, headers={"HX-Redirect": url}
        url=url,
        status_code=status_code,
    )


def redirect_with_error(
    request: Request, url: str, error: str, status_code=302
) -> Response:
    return redirect_with_query_params(request, url, {"error": error}, status_code)


def generate_uuid() -> str:
    return str(uuid4())
