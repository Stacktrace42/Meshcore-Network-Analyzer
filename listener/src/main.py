"""Main application for Meshcore Network Analyzer Listener component."""
import asyncio
import logging
import signal
import sys

from .config import settings
from .device_manager import DeviceManager
from .packet_listener import PacketListener
from .contact_manager import ContactManager
from .api_client import ProcessingAPIClient
from .trace_handler import TraceHandler

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ListenerService:
    """Main service for the Listener component."""

    def __init__(self):
        self.device_manager = DeviceManager()
        self.api_client = ProcessingAPIClient()
        self.running = False
        self.packet_listener = None
        self.contact_manager = None
        self.trace_handler = None

    async def data_callback(self, data_type: str, data: dict):
        """Callback for sending data to Processing API."""
        await self.api_client.send_data(data_type, data)

    async def start(self):
        """Start the listener service."""
        logger.info("Starting Meshcore Network Analyzer Listener")
        logger.info(f"Listener ID: {settings.listener_id}")
        logger.info(f"Device: {settings.device_path}")
        logger.info(f"Processing URL: {settings.processing_url}")

        self.running = True

        try:
            # Connect to MeshCore device
            meshcore = await self.device_manager.connect()

            # Initialize components
            # Note: Create packet_listener first so trace_handler can use it for gateway selection
            self.packet_listener = PacketListener(self.data_callback, trace_handler=None)
            self.trace_handler = TraceHandler(meshcore, self.api_client, self.packet_listener)
            self.contact_manager = ContactManager(self.data_callback)

            # Now connect trace_handler to packet_listener
            self.packet_listener.trace_handler = self.trace_handler

            # Register packet listeners
            self.packet_listener.register_handlers(meshcore)

            # Start auto message fetching (for new incoming messages)
            await meshcore.start_auto_message_fetching()
            logger.info("Auto message fetching started")

            # Fetch all stored contacts from device storage (up to 350)
            logger.info("Fetching stored contacts from device...")
            await self.contact_manager.fetch_contacts(meshcore)

            # Pull all stored messages from device storage
            logger.info("Pulling stored messages from device...")
            try:
                message_count = 0
                processed_count = 0
                max_messages = 1000  # Safety limit
                while message_count < max_messages:
                    msg_result = await meshcore.commands.get_msg()
                    if hasattr(msg_result, 'type'):
                        if msg_result.type.name == 'ERROR':
                            logger.debug(f"No more messages in storage (pulled {message_count})")
                            break
                        if msg_result.payload:
                            message_count += 1
                            # Process the stored message through packet listener
                            await self.packet_listener.process_stored_message(msg_result)
                            processed_count += 1
                        else:
                            break
                    else:
                        break

                if message_count > 0:
                    logger.info(f"Retrieved and processed {processed_count}/{message_count} stored messages from device")
                else:
                    logger.info("No stored messages found on device")
            except Exception as e:
                logger.warning(f"Error pulling stored messages: {e}")

            # Start background tasks
            contact_task = asyncio.create_task(self._periodic_contact_fetch())
            trace_task = asyncio.create_task(self._periodic_trace_poll())
            health_task = asyncio.create_task(self._health_check())
            gateway_task = asyncio.create_task(self._periodic_gateway_update())

            logger.info("Listener service started successfully")

            # Wait for tasks
            await asyncio.gather(
                contact_task,
                trace_task,
                health_task,
                gateway_task,
                return_exceptions=True
            )

        except Exception as e:
            logger.error(f"Error in listener service: {e}", exc_info=True)
            self.running = False
            raise

    async def _periodic_contact_fetch(self):
        """Periodically fetch contacts from device."""
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                if self.device_manager.is_connected():
                    logger.info("Fetching contacts...")
                    meshcore = self.device_manager.meshcore
                    await self.contact_manager.fetch_contacts(meshcore)
                else:
                    logger.warning("Device not connected, skipping contact fetch")

            except Exception as e:
                logger.error(f"Error in contact fetch loop: {e}")

    async def _periodic_trace_poll(self):
        """Periodically poll for and execute trace commands."""
        while self.running:
            try:
                await asyncio.sleep(settings.poll_interval_seconds)

                if self.device_manager.is_connected():
                    logger.debug("Polling for traces...")
                    await self.trace_handler.poll_and_execute_traces()
                else:
                    logger.warning("Device not connected, skipping trace poll")

            except Exception as e:
                logger.error(f"Error in trace poll loop: {e}")

    async def _periodic_gateway_update(self):
        """Periodically log and update the best gateway repeater."""
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                if self.packet_listener:
                    best_hash, best_snr = self.packet_listener.get_best_repeater(self.contact_manager)
                    if best_hash:
                        logger.info(f"Best gateway repeater: {best_hash} with SNR {best_snr:.2f} dB")
                        logger.info(f"Total repeaters observed: {len(self.packet_listener.repeater_snr)}")
                    else:
                        logger.warning("No repeaters with SNR data yet")

            except Exception as e:
                logger.error(f"Error in gateway update: {e}")

    async def _health_check(self):
        """Periodic health check and reconnection."""
        while self.running:
            try:
                await asyncio.sleep(60)  # Every minute

                if not self.device_manager.is_connected():
                    logger.warning("Device connection lost, attempting reconnect...")
                    await self.device_manager.ensure_connected()

                    # After reconnection, pull stored contacts and messages
                    if self.device_manager.is_connected():
                        logger.info("Reconnected - pulling stored data from device...")
                        meshcore = self.device_manager.meshcore

                        # Fetch all stored contacts
                        await self.contact_manager.fetch_contacts(meshcore)

                        # Pull all stored messages
                        try:
                            message_count = 0
                            processed_count = 0
                            max_messages = 1000
                            while message_count < max_messages:
                                msg_result = await meshcore.commands.get_msg()
                                if hasattr(msg_result, 'type'):
                                    if msg_result.type.name == 'ERROR':
                                        break
                                    if msg_result.payload:
                                        message_count += 1
                                        # Process the stored message
                                        await self.packet_listener.process_stored_message(msg_result)
                                        processed_count += 1
                                    else:
                                        break
                                else:
                                    break

                            if message_count > 0:
                                logger.info(f"Pulled and processed {processed_count}/{message_count} stored messages after reconnect")
                        except Exception as e:
                            logger.warning(f"Error pulling stored messages after reconnect: {e}")

            except Exception as e:
                logger.error(f"Error in health check: {e}")

    async def stop(self):
        """Stop the listener service."""
        logger.info("Stopping listener service...")
        self.running = False

        # Disconnect from device
        await self.device_manager.disconnect()

        # Close API client
        await self.api_client.close()

        logger.info("Listener service stopped")


# Global service instance
service = None


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    if service:
        asyncio.create_task(service.stop())
    sys.exit(0)


async def main():
    """Main entry point."""
    global service

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and start service
    service = ListenerService()

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
