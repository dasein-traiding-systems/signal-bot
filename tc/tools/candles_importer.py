from tools.candles_importer.importer import CandlesImporter
import logging
import asyncio

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    ce = CandlesImporter()

    async def main():
        await ce.init()
        await ce.import_all()

    asyncio.run(main())
