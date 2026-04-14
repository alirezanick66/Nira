# ==================== Imports ====================
import asyncio
# ==================== Imports داخلی پروژه ====================
from src.config.logging_config import log_message, LogLevel, LG
from src.data.fetchers.digikala_api import DigikalaAPIClient


async def main():
    async with DigikalaAPIClient() as client:
        response = await client.fetch_product_list()


if __name__ == "__main__":
    asyncio.run( main() )
