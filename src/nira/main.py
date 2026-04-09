# ==================== Imports ====================
import asyncio
from pathlib import Path
# ==================== Imports داخلی پروژه ====================
from nira.data.scraping.detail_scraper import scrape_products
from nira.data.scraping.list_scraper import collect_all_ids, load_ids, save_ids
from nira.config.logging_config import log_message, LogLevel, LG


async def main():
    log_message( LG.SCRAPING, "شروع جمع‌آوری ID محصولات...", LogLevel.INFO )
    all_ids = await collect_all_ids()
    save_ids( all_ids, output_path=Path( "data/products/product_ids.json" ) )
    ids = load_ids( Path( "data/products/product_ids.json" ) )
    await scrape_products( ids[ :5 ], Path( "data/products/products.json" ) )


asyncio.run( main() )
