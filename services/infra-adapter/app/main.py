"""InfraMind Adapter main application."""

import asyncio
import logging
import signal
from typing import Optional

from app.adapter import InfraMindAdapter
from app.config import Settings, get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class Application:
    """Main application orchestrator."""

    def __init__(self, settings: Settings):
        """
        Initialize application.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.adapter: Optional[InfraMindAdapter] = None
        self._shutdown = False

    async def start(self) -> None:
        """Start the application."""
        logger.info("🚀 Starting Sentinel InfraMind Adapter...")
        logger.info(f"   Version: {__import__('app').__version__}")
        logger.info(f"   InfraMind URL: {self.settings.inframind_url}")
        logger.info(f"   Telemetry Interval: {self.settings.telemetry_batch_interval_seconds}s")

        # Initialize adapter
        self.adapter = InfraMindAdapter(self.settings)
        await self.adapter.start()

        logger.info("✓ InfraMind Adapter started successfully")

        # Run until shutdown signal
        try:
            while not self._shutdown:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the application."""
        logger.info("🛑 Shutting down InfraMind Adapter...")
        self._shutdown = True

        if self.adapter:
            await self.adapter.stop()

        logger.info("✓ InfraMind Adapter stopped")

    def handle_signal(self, sig: int) -> None:
        """
        Handle shutdown signals.

        Args:
            sig: Signal number
        """
        logger.info(f"Received signal {sig}, initiating shutdown...")
        self._shutdown = True


async def main() -> None:
    """Main entry point."""
    settings = get_settings()
    app = Application(settings)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, app.handle_signal, sig)

    try:
        await app.start()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
