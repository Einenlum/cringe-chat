from urllib import parse

from fastapi.responses import RedirectResponse


def encode_query_params(params: dict) -> str:
    return parse.urlencode(params)


def redirect_with_query_params(url: str, params: dict) -> RedirectResponse:
    query_params = encode_query_params(params)
    # return redirect response
    return RedirectResponse(url=f"{url}?{query_params}", status_code=302)


def redirect_with_error(url: str, error: str) -> RedirectResponse:
    return redirect_with_query_params(url, {"error": error})
