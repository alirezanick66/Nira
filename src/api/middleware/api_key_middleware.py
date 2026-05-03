"""
‫میان‌افزار احراز هویت API Key (نسخه ساده‌شده)
کلید دریافتی را مستقیماً با کلید تنظیم‌شده در‫ .env مقایسه می‌کند.
"""
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger( __name__ )

# مسیرهایی که نیاز به احراز هویت ندارند
_PUBLIC_PATHS: frozenset[ str ] = frozenset( { "/", "/docs", "/openapi.json", "/redoc", "/health" } )

# ✅ افزودن پسوند فایل‌های استاتیک به لیست سفید
_STATIC_EXTENSIONS: frozenset[ str ] = frozenset(
    { ".css", ".js", ".ico", ".png", ".jpg", ".jpeg", ".svg", ".woff", ".woff2", ".ttf", ".eot", ".map", ".json" } )


class ApiKeyMiddleware( BaseHTTPMiddleware ):
    """
    بررسی هدر X-API-Key و تزریق store_id به request.state.
    در صورت نامعتبر بودن کلید، پاسخ 401 استاندارد برمی‌گرداند.
    """

    def __init__( self, app, api_key: str ) -> None:
        super().__init__( app )
        self._api_key = api_key

    async def dispatch( self, request: Request, call_next ) -> Response:
        # ۱. مسیرهای عمومی بدون بررسی رد می‌شوند
        if request.url.path in _PUBLIC_PATHS:
            return await call_next( request )

        # ۲. فایل‌های استاتیک (CSS, JS, Images, Fonts, etc.)
        if any( request.url.path.lower().endswith( ext ) for ext in _STATIC_EXTENSIONS ):
            return await call_next( request )

        # ۳. استخراج کلید API (اولویت با هدر X-API-Key، فال‌بک روی کوئری پارامتر برای EventSource)
        client_key = request.headers.get( "X-API-Key", "" ).strip()
        if not client_key:
            client_key = request.query_params.get( "api_key", "" ).strip()

        # ۴. اعتبارسنجی کلید
        if not client_key or client_key != self._api_key:
            logger.warning( "❌ درخواست با کلید نامعتبر — path=%s", request.url.path )
            return JSONResponse(
                status_code=401,
                content={ "detail": "Unauthorized: Invalid or missing API Key" },
            )

        # ۵. در صورت معتبر بودن، شناسه پیش‌فرض تزریق می‌شود
        request.state.store_id = "default_store"
        return await call_next( request )
