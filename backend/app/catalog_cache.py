"""Only explicitly public, successful catalog responses may enter shared caches."""
import hashlib
import re
from urllib.parse import parse_qs

from starlette.datastructures import Headers, MutableHeaders


class CatalogCacheMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        public = scope["method"] in {"GET", "HEAD"} and (
            path in {"/api/v1/catalog", "/api/v1/projects", "/api/v1/project-aliases", "/api/v1/chairs", "/api/v1/departments", "/api/v1/facets"}
            or bool(re.fullmatch(r"/api/v1/catalog/[^/]+|/api/v1/projects/[^/]+(?:/(?:detail|profile|description))?", path)))
        immutable = path.startswith("/api/v1/catalog/") or (path.endswith("/detail") and bool(parse_qs(scope.get("query_string", b"").decode()).get("version")))
        if not public:
            async def private_send(message):
                if message["type"] == "http.response.start":
                    MutableHeaders(scope=message)["cache-control"] = "private, no-store"
                await send(message)
            return await self.app(scope, receive, private_send)
        start = None
        chunks = []
        async def cached_send(message):
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    body = b"".join(chunks)
                    headers = MutableHeaders(scope=start)
                    if start["status"] == 200:
                        headers["cache-control"] = "public, max-age=31536000, immutable" if immutable else "public, max-age=0, s-maxage=300, must-revalidate"
                        etag = '"' + hashlib.sha256(body).hexdigest() + '"'
                        headers["etag"] = etag
                        candidates = Headers(scope=scope).get("if-none-match", "").split(",")
                        if any(v.strip().removeprefix("W/") in {etag, "*"} for v in candidates):
                            start["status"] = 304
                            body = b""
                            del headers["content-length"]
                    else:
                        headers["cache-control"] = "no-store"
                    await send(start)
                    await send({"type": "http.response.body", "body": body})
        await self.app(scope, receive, cached_send)
