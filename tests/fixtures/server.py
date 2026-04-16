"""Local FastAPI app serving deterministic pages for tests."""

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

_PAGES = Path(__file__).parent / "pages"


def read(name: str) -> str:
    return (_PAGES / name).read_text(encoding="utf-8")


def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/static/article", response_class=HTMLResponse)
    def static_article() -> str:
        return read("static.html")

    @app.get("/spa/app", response_class=HTMLResponse)
    def spa() -> str:
        return read("spa.html")

    @app.get("/auth/private")
    def auth_private(request: Request) -> Response:
        if request.cookies.get("fixture_auth") != "1":
            return Response("unauthorized", status_code=401)
        return HTMLResponse(read("auth_private.html"))

    @app.get("/auth/login")
    def auth_login(response: Response) -> Response:
        resp = HTMLResponse("<p>logged in</p>")
        resp.set_cookie("fixture_auth", "1", path="/", max_age=86400)
        return resp

    @app.get("/challenge/cloudflare", response_class=HTMLResponse)
    def challenge() -> str:
        return read("challenge_cloudflare.html")

    @app.get("/table/large", response_class=HTMLResponse)
    def tables() -> str:
        return read("tables.html")

    @app.get("/forms/login", response_class=HTMLResponse)
    def forms() -> str:
        return read("forms.html")

    @app.get("/images/mixed", response_class=HTMLResponse)
    def images() -> str:
        return read("images.html")

    @app.get("/links/mixed", response_class=HTMLResponse)
    def links() -> str:
        return read("links.html")

    @app.get("/slow")
    def slow() -> PlainTextResponse:
        import time

        time.sleep(5)
        return PlainTextResponse("slow")

    @app.get("/redirect-loop")
    def redirect_loop() -> RedirectResponse:
        return RedirectResponse("/redirect-loop")

    @app.get("/oversize")
    def oversize() -> PlainTextResponse:
        return PlainTextResponse("x" * (60 * 1024 * 1024))

    @app.get("/img/{name}")
    def image_asset(name: str) -> Response:
        return Response(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, media_type="image/png")

    return app
