"""MeshCore device connection management."""
import asyncio
import logging
from meshcore import MeshCore
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages connection to MeshCore hardware device."""

    def __init__(self):
        self.meshcore: Optional[MeshCore] = None
        self.connected = False
        self.reconnect_delay = 5  # seconds

    async def connect(self) -> MeshCore:
        """
        Connect to MeshCore device via serial.

        Retries on failure with exponential backoff.
        """
        retry_count = 0
        max_retries = 10

        while retry_count < max_retries:
            try:
                logger.info(
                    f"Connecting to MeshCore device at {settings.device_path} "
                    f"(attempt {retry_count + 1}/{max_retries})"
                )

                self.meshcore = await MeshCore.create_serial(
                    settings.device_path,
                    settings.device_baud_rate,
                    debug=(settings.log_level == "DEBUG")
                )

                self.connected = True
                logger.info("Successfully connected to MeshCore device")

                # Get device info (send_appstart in newer versions)
                try:
                    device_info = await self.meshcore.send_appstart()
                    logger.info(f"Device info: {device_info}")
                except Exception as e:
                    logger.warning(f"Could not get device info: {e}")

                logger.info("Device connection established - ready to pull stored data")
                return self.meshcore

            except Exception as e:
                retry_count += 1
                logger.error(f"Failed to connect to device: {e}")

                if retry_count < max_retries:
                    delay = min(self.reconnect_delay * (2 ** retry_count), 60)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries reached, giving up")
                    raise

    async def ensure_connected(self):
        """Ensure device is connected, reconnect if needed."""
        if not self.connected or not self.meshcore:
            await self.connect()

        # Check connection health
        if not self.meshcore.is_connected:
            logger.warning("Device disconnected, reconnecting...")
            self.connected = False
            await self.connect()

    async def disconnect(self):
        """Disconnect from device."""
        if self.meshcore:
            try:
                # MeshCore disconnect method (if available)
                # await self.meshcore.disconnect()
                self.connected = False
                logger.info("Disconnected from MeshCore device")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self.connected and self.meshcore is not None and self.meshcore.is_connected
