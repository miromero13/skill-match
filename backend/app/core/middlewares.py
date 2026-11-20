import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send
from app.core.config import settings

class SecurityHeadersMiddleware:
    """
    Middleware ASGI puro para inyectar cabeceras de seguridad HTTP básicas y métricas de tiempo de ejecución.
    Evita deadlocks y fugas de conexiones en el pool ante desconexiones o cancelaciones del cliente.
    """
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.perf_counter() - start_time
                headers = MutableHeaders(scope=message)
                headers["X-Process-Time"] = f"{process_time:.4f}s"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["X-XSS-Protection"] = "1; mode=block"
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_middlewares(app: FastAPI) -> None:
    """Configura la cadena de middlewares de la aplicación."""
    # Cabeceras de seguridad y métrica de tiempo
    app.add_middleware(SecurityHeadersMiddleware)

    # Compresión GZip para respuestas mayores a 1000 bytes
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS (añadido al final para que sea el middleware más externo y garantice cabeceras en toda respuesta)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
