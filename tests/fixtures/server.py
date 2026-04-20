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

    @app.get("/crawl/", response_class=HTMLResponse)
    @app.get("/crawl/index", response_class=HTMLResponse)
    def crawl_index() -> str:
        return read("crawl_index.html")

    @app.get("/crawl/a", response_class=HTMLResponse)
    def crawl_a() -> str:
        return read("crawl_a.html")

    @app.get("/crawl/a1", response_class=HTMLResponse)
    def crawl_a1() -> str:
        return read("crawl_a1.html")

    @app.get("/crawl/a2", response_class=HTMLResponse)
    def crawl_a2() -> str:
        return read("crawl_a2.html")

    @app.get("/crawl/b", response_class=HTMLResponse)
    def crawl_b() -> str:
        return read("crawl_b.html")

    @app.get("/crawl/b1", response_class=HTMLResponse)
    def crawl_b1() -> str:
        return read("crawl_b1.html")

    @app.get("/crawl/admin/secret", response_class=HTMLResponse)
    def crawl_admin_secret() -> str:
        return read("crawl_admin_secret.html")

    @app.get("/crawl/loop", response_class=HTMLResponse)
    def crawl_loop() -> str:
        return read("crawl_loop.html")

    @app.get("/crawl/slow-page", response_class=HTMLResponse)
    def crawl_slow_page() -> str:
        import time

        time.sleep(3)
        return "<html><body><p>slow page body</p></body></html>"

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots_txt() -> str:
        return read("robots.txt")

    @app.get("/img/missing.png")
    def missing_img() -> Response:
        return Response("not found", status_code=404)

    @app.get("/img/huge.png")
    def huge_img() -> Response:
        return Response(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * (60 * 1024 * 1024),
            media_type="image/png",
        )

    @app.get("/img/not-image.png")
    def not_image() -> Response:
        return Response("<html>not an image</html>", media_type="text/html")

    @app.get("/img/{name}")
    def image_asset(name: str) -> Response:
        return Response(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, media_type="image/png")

    return app
