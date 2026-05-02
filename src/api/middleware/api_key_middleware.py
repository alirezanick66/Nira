"""
میان‌افزار احراز هویت API Key
کلید دریافتی را Validate کرده و به store_id مپ می‌کند.
کلید خام هرگز در لاگ ثبت نمی‌شود.
"""

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger( __name__ )

# مسیرهایی که نیازی به API Key ندارند
_PUBLIC_PATHS: frozenset[ str ] = frozenset( { "/", "/docs", "/openapi.json", "/health" } )


class ApiKeyMiddleware( BaseHTTPMiddleware ):
    """
    بررسی هدر X-API-Key و تزریق store_id به request.state.
    در صورت کلید نامعتبر، پاسخ 401 برمی‌گرداند.
    """

    def __init__( self, app, api_key_store_map: dict[ str, str ] ) -> None:
        """
        :param api_key_store_map: نگاشت {api_key: store_id} — از Settings بارگذاری می‌شود.
        """
        super().__init__( app )
        self._key_map = api_key_store_map

    async def dispatch( self, request: Request, call_next ) -> Response:
        # مسیرهای عمومی نیازی به بررسی ندارند
        if request.url.path in _PUBLIC_PATHS:
            return await call_next( request )

        api_key = request.headers.get( "X-API-Key", "" ).strip()

        store_id = self._key_map.get( api_key )
        if not store_id:
            logger.warning( "درخواست با کلید نامعتبر — path=%s", request.url.path )
            return JSONResponse( status_code=401, content={ "detail": "Unauthorized" } )

        # store_id (نه کلید خام) به request.state تزریق می‌شود
        request.state.store_id = store_id
        return await call_next( request )
