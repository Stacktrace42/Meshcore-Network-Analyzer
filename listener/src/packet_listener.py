"""Packet listening and path extraction."""
import asyncio
import logging
from meshcore import EventType
from typing import Callable, Dict, Any
from datetime import datetime

from .config import settings

logger = logging.getLogger(__name__)


class PacketListener:
    """Listens to MeshCore packets and extracts path information."""

    def __init__(self, data_callback: Callable, trace_handler=None):
        """
        Initialize packet listener.

        Args:
            data_callback: Async function to call with extracted data
            trace_handler: Optional TraceHandler instance for handling trace responses
        """
        self.data_callback = data_callback
        self.trace_handler = trace_handler
        self.handlers_registered = False
        self.rx_subscription = None
        self.msg_subscription = None
        self.repeater_snr = {}  # Maps hash -> best SNR observed

    def register_handlers(self, meshcore):
        """Register event handlers with MeshCore device."""
        if self.handlers_registered:
            return

        # Subscribe to RX_LOG_DATA - it captures all raw RF packets
        self.rx_subscription = meshcore.subscribe(
            EventType.RX_LOG_DATA,
            self._handle_rx_log
        )

        self.handlers_registered = True
        logger.info("Packet listener registered for RX_LOG_DATA events")

    def _handle_rx_log(self, event):
        """
        Handle RX_LOG_DATA event - received packet log.

        NOTE: This is a synchronous function as required by meshcore library.
        """
        try:
            payload = event.payload

            if not isinstance(payload, dict):
                return

            # Get SNR and RSSI from the event
            snr = payload.get("snr")
            rssi = payload.get("rssi")

            # Get the packet payload (hex string)
            packet_hex = payload.get("payload")
            if not packet_hex:
                return

            logger.info(f"RX log received - SNR: {snr}, RSSI: {rssi}, parsing packet...")

            # Parse the MeshCore packet structure
            path_data = self._parse_meshcore_packet(packet_hex, snr, rssi)

            if path_data:
                logger.info(f"Extracted path: {path_data['path']}")

                # Track SNR for repeaters in the path
                if snr is not None:
                    for hop_hash in path_data['path']:
                        # Update best SNR for this repeater
                        current_best = self.repeater_snr.get(hop_hash, float('-inf'))
                        if snr > current_best:
                            self.repeater_snr[hop_hash] = snr
                            logger.debug(f"Updated best SNR for {hop_hash}: {snr}")

                # Schedule the async callback in the event loop
                asyncio.create_task(self.data_callback("path", path_data))
            else:
                logger.debug("No valid path found in packet")

            # Also check for trace responses (PAYLOAD_TYPE_PATH packets)
            trace_response = self._parse_trace_response(packet_hex, snr, rssi)
            if trace_response and self.trace_handler:
                logger.info(f"Extracted trace response with tag {trace_response['tag']}")
                self.trace_handler.on_trace_response(
                    tag=trace_response['tag'],
                    path=trace_response['path'],
                    snr_values=trace_response['snr_values']
                )

        except Exception as e:
            logger.error(f"Error handling RX log: {e}", exc_info=True)

    def _parse_meshcore_packet(self, packet_hex: str, snr: float = None, rssi: float = None):
        """
        Parse MeshCore packet structure to extract path information.

        Packet structure:
        - header (1 byte): route type, payload type, payload version
        - transport_codes (4 bytes, optional): only if route type is TRANSPORT_*
        - path_len (1 byte): length of path field in bytes
        - path (variable, up to 64 bytes): routing path (array of node hashes)
        - payload (rest): actual data

        Args:
            packet_hex: Hex string of packet bytes
            snr: Signal-to-Noise Ratio
            rssi: Received Signal Strength Indicator

        Returns:
            Dict with path data or None if no valid path
        """
        try:
            # Convert hex string to bytes
            packet_bytes = bytes.fromhex(packet_hex)

            if len(packet_bytes) < 2:
                return None

            # Parse header byte
            header = packet_bytes[0]
            route_type = header & 0x03  # bits 0-1
            payload_type = (header & 0x3C) >> 2  # bits 2-5
            payload_version = (header & 0xC0) >> 6  # bits 6-7

            # Route types:
            # 0x00 = ROUTE_TYPE_TRANSPORT_FLOOD (has transport codes)
            # 0x01 = ROUTE_TYPE_FLOOD (builds up path)
            # 0x02 = ROUTE_TYPE_DIRECT (path is supplied)
            # 0x03 = ROUTE_TYPE_TRANSPORT_DIRECT (has transport codes)

            offset = 1

            # Skip transport codes if present (route types 0x00 or 0x03)
            if route_type in (0x00, 0x03):
                offset += 4  # Skip 4 bytes of transport codes

            if offset >= len(packet_bytes):
                return None

            # Get path length
            path_len = packet_bytes[offset]
            offset += 1

            # Check if we have enough bytes for the path
            if path_len == 0 or offset + path_len > len(packet_bytes):
                return None

            # Extract path (array of node hashes, 1 byte each)
            path_bytes = packet_bytes[offset:offset + path_len]
            path_hashes = [f"0x{b:02x}" for b in path_bytes]

            # Need at least 2 hops for a meaningful path
            if len(path_hashes) < 2:
                return None

            # Source is first hop, destination is last hop
            source_hash = path_hashes[0]
            dest_hash = path_hashes[-1]

            return {
                "source_hash": source_hash,
                "dest_hash": dest_hash,
                "path": path_hashes,
                "snr": snr,
                "rssi": rssi
            }

        except Exception as e:
            logger.debug(f"Could not parse packet as MeshCore packet: {e}")
            return None

    def _parse_trace_response(self, packet_hex: str, snr: float = None, rssi: float = None):
        """
        Parse trace response packet (PAYLOAD_TYPE_TRACE = 0x09).

        Trace responses contain the path with SNR values for each hop.

        Args:
            packet_hex: Hex string of packet bytes
            snr: Signal-to-Noise Ratio of the received packet
            rssi: Received Signal Strength Indicator

        Returns:
            Dict with trace response data or None
        """
        try:
            # Convert hex string to bytes
            packet_bytes = bytes.fromhex(packet_hex)

            if len(packet_bytes) < 2:
                return None

            # Parse header byte
            header = packet_bytes[0]
            route_type = header & 0x03
            payload_type = (header & 0x3C) >> 2

            # Check if this is a trace payload (0x09)
            if payload_type != 0x09:
                return None

            logger.info(f"Found PAYLOAD_TYPE_TRACE packet")

            offset = 1

            # Skip transport codes if present
            if route_type in (0x00, 0x03):
                offset += 4

            if offset >= len(packet_bytes):
                return None

            # Get path length
            path_len = packet_bytes[offset]
            offset += 1

            if path_len == 0 or offset + path_len > len(packet_bytes):
                return None

            # Extract path
            path_bytes = packet_bytes[offset:offset + path_len]
            path_hashes = [f"0x{b:02x}" for b in path_bytes]
            offset += path_len

            # After the path, trace packets may contain additional data
            # including tag and SNR values for each hop
            # The exact format needs to be determined from MeshCore documentation

            # Try to extract tag (4 bytes after path)
            tag = None
            snr_values = []

            if offset + 4 <= len(packet_bytes):
                tag = int.from_bytes(packet_bytes[offset:offset+4], byteorder='little')
                offset += 4
                logger.info(f"Extracted trace tag: {tag}")

                # Try to extract SNR values (signed bytes, SNR*4)
                # One SNR value per hop in the path
                if offset + len(path_hashes) <= len(packet_bytes):
                    for i in range(len(path_hashes)):
                        if offset < len(packet_bytes):
                            snr_byte = packet_bytes[offset]
                            # Convert from signed byte
                            snr_value = snr_byte if snr_byte < 128 else snr_byte - 256
                            # Divide by 4 to get actual SNR
                            snr_values.append(snr_value / 4.0)
                            offset += 1

            if tag is not None:
                return {
                    "tag": tag,
                    "path": path_hashes,
                    "snr_values": snr_values
                }

            return None

        except Exception as e:
            logger.debug(f"Could not parse packet as trace response: {e}")
            return None

    def get_best_repeater(self, contact_manager=None):
        """
        Get the repeater with the best (highest) SNR.

        Args:
            contact_manager: Optional ContactManager to filter only known repeaters

        Returns:
            Tuple of (hash, snr) for the best repeater, or (None, None) if none found
        """
        if not self.repeater_snr:
            logger.warning("No repeater SNR data available yet")
            return None, None

        # Get repeater hashes that are confirmed as repeaters
        valid_repeaters = self.repeater_snr.keys()

        if contact_manager and hasattr(contact_manager, 'contacts'):
            # Filter to only hashes we know are repeaters
            repeater_contacts = {
                hash: contact for hash, contact in contact_manager.contacts.items()
                if contact.get('is_repeater', False)
            }
            valid_repeaters = [
                hash for hash in self.repeater_snr.keys()
                if hash in repeater_contacts
            ]

        if not valid_repeaters:
            logger.warning("No valid repeaters with SNR data")
            return None, None

        # Find the best repeater by SNR
        best_hash = max(valid_repeaters, key=lambda h: self.repeater_snr.get(h, float('-inf')))
        best_snr = self.repeater_snr[best_hash]

        logger.info(f"Best repeater: {best_hash} with SNR {best_snr}")
        return best_hash, best_snr

    async def process_stored_message(self, msg_result):
        """
        Process a message retrieved from device storage.

        Args:
            msg_result: Result from meshcore.commands.get_msg()
        """
        # Stored messages don't typically have path info in the same format
        # We'll skip processing these for now since we're getting paths from RX_LOG_DATA
        pass
