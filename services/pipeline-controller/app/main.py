"""Pipeline Controller main application."""

import asyncio
import logging
import signal
from typing import Optional

from app.config import Settings, get_settings
from app.controller import PipelineController

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
        self.controller: Optional[PipelineController] = None
        self._shutdown = False

    async def start(self) -> None:
        """Start the application."""
        logger.info("🚀 Starting Sentinel Pipeline Controller...")
        logger.info(f"   Version: {__import__('app').__version__}")
        logger.info(f"   Kafka: {self.settings.kafka_bootstrap_servers}")
        logger.info(f"   Policy Engine Mode: {self.settings.policy_engine_mode}")

        # Initialize controller
        self.controller = PipelineController(self.settings)
        await self.controller.start()

        logger.info("✓ Pipeline Controller started successfully")

        # Run until shutdown signal
        try:
            while not self._shutdown:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the application."""
        logger.info("🛑 Shutting down Pipeline Controller...")
        self._shutdown = True

        if self.controller:
            await self.controller.stop()

        logger.info("✓ Pipeline Controller stopped")

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
