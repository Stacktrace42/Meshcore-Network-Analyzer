"""Trace command execution handler."""
import logging
import asyncio
import random
from typing import Dict, Any, Optional
from meshcore.events import EventType

logger = logging.getLogger(__name__)


class TraceHandler:
    """Handles execution of trace commands."""

    def __init__(self, meshcore, api_client, packet_listener=None):
        """
        Initialize trace handler.

        Args:
            meshcore: MeshCore device instance
            api_client: ProcessingAPIClient instance
            packet_listener: PacketListener for gateway selection
        """
        self.meshcore = meshcore
        self.api_client = api_client
        self.packet_listener = packet_listener
        self.active_traces = {}
        self.pending_traces = {}  # Maps tag -> asyncio.Future for trace responses
        self._gateway_hash = None  # Cached best gateway repeater

    def _get_gateway_repeater(self) -> Optional[str]:
        """
        Get the best gateway repeater (nearest repeater with best SNR).

        Returns:
            Hash of the gateway repeater, or None if not available
        """
        if not self.packet_listener:
            logger.warning("No packet listener available for gateway selection")
            return None

        # Try to get best repeater from SNR data
        best_hash, best_snr = self.packet_listener.get_best_repeater()

        if best_hash:
            if self._gateway_hash != best_hash:
                self._gateway_hash = best_hash
                logger.info(f"Gateway repeater updated to {best_hash} (SNR: {best_snr:.2f} dB)")
            return best_hash

        logger.warning("No gateway repeater available yet")
        return None

    def _format_trace_path(self, path_hashes: list, snr_values: list) -> str:
        """
        Format trace path with SNR values.

        Args:
            path_hashes: List of repeater hashes in the path
            snr_values: List of SNR values for each hop

        Returns:
            Formatted string like "0xa0(-3.4)→0x41(12.0)→0x1c(8.5)"
        """
        if not path_hashes:
            return ""

        formatted_hops = []
        for i, hop_hash in enumerate(path_hashes):
            if i < len(snr_values):
                snr = snr_values[i]
                formatted_hops.append(f"{hop_hash}({snr:.1f})")
            else:
                formatted_hops.append(hop_hash)

        return "→".join(formatted_hops)

    async def execute_trace(self, trace_info: Dict[str, Any]):
        """
        Execute a trace command to verify an edge using a loop path.

        To verify edge A→B with gateway X:
        - Send trace: X → B → A → X (loop back to gateway)
        - This verifies the path exists and we can receive the response

        The trace MUST return to the gateway repeater so we can decrypt the response.

        Args:
            trace_info: Trace information from Processing API
        """
        trace_id = trace_info.get("id")
        from_hash = trace_info.get("from_repeater_hash")  # Source of edge
        to_hash = trace_info.get("to_repeater_hash")  # Destination of edge
        to_pubkey = trace_info.get("to_repeater_public_key")

        logger.info(f"Executing trace {trace_id}: verifying edge {from_hash}→{to_hash}")

        try:
            # Claim the trace
            claimed = await self.api_client.claim_trace(trace_id)
            if not claimed:
                logger.warning(f"Failed to claim trace {trace_id}")
                return

            # Execute trace using MeshCore
            # In MeshCore, traces are typically sent as CLI commands
            # Format: "trace <destination>"

            # Get gateway repeater (nearest repeater with best SNR)
            gateway_hash = self._get_gateway_repeater()

            if not gateway_hash:
                logger.error(f"No gateway repeater available for trace {trace_id}")
                await self.api_client.submit_trace_result(
                    trace_id,
                    success=False,
                    error="No gateway repeater available"
                )
                return

            # Build loop path: Gateway → To → From → Gateway
            # This verifies edge From→To by checking reverse path To→From
            # and ensures response comes back through gateway
            trace_path = f"{gateway_hash.replace('0x', '')},{to_hash.replace('0x', '')}"

            # Add return path through from_hash if it's different from gateway
            if from_hash and from_hash != gateway_hash:
                trace_path += f",{from_hash.replace('0x', '')}"

            # Close the loop back to gateway
            trace_path += f",{gateway_hash.replace('0x', '')}"

            logger.info(f"Trace {trace_id} path: {trace_path}")

            # Send trace command using MeshCore
            try:
                # Generate unique tag for this trace
                tag = random.randint(1, 0xFFFFFFFF)

                # Send trace with loop path
                result = await self.meshcore.commands.send_trace(
                    path=trace_path,
                    tag=tag
                )

                if result.type == EventType.ERROR:
                    logger.error(f"Trace {trace_id} failed to send: {result.payload}")
                    await self.api_client.submit_trace_result(
                        trace_id,
                        success=False,
                        error=f"Send failed: {result.payload}"
                    )
                    return

                logger.info(f"Trace {trace_id} sent with tag {tag}, waiting for response...")

                # Create a Future to wait for the trace response
                response_future = asyncio.Future()
                self.pending_traces[tag] = response_future

                # Poll for messages - trace responses might come through message system
                asyncio.create_task(self._poll_for_trace_response(tag))

                # Wait for trace data response (delivered via on_trace_response callback or polling)
                try:
                    trace_response = await asyncio.wait_for(response_future, timeout=30.0)

                    # Extract path and SNR from response
                    path_hashes = trace_response.get("path", [])
                    snr_values = trace_response.get("snr_values", [])

                    # Check if the expected intermediate hop (from_hash) is in the path
                    edge_verified = from_hash in path_hashes if from_hash else False

                    # Format path with SNR values: "A(-3.4)→B(12.0)→C(8.5)"
                    formatted_path = self._format_trace_path(path_hashes, snr_values)

                    logger.info(
                        f"Trace {trace_id} completed: {formatted_path}, edge_verified={edge_verified}"
                    )

                    await self.api_client.submit_trace_result(
                        trace_id,
                        success=True,
                        path=path_hashes if path_hashes else None,
                        snr_values=snr_values if snr_values else None,
                        formatted_path=formatted_path,
                        error=None
                    )

                except asyncio.TimeoutError:
                    logger.warning(f"Trace {trace_id} timed out waiting for response")
                    await self.api_client.submit_trace_result(
                        trace_id,
                        success=False,
                        error="Timeout waiting for trace response"
                    )
                finally:
                    # Clean up pending trace
                    self.pending_traces.pop(tag, None)

            except Exception as e:
                logger.error(f"Error sending trace command: {e}", exc_info=True)
                await self.api_client.submit_trace_result(
                    trace_id,
                    success=False,
                    error=str(e)
                )

        except Exception as e:
            logger.error(f"Error executing trace {trace_id}: {e}")
            await self.api_client.submit_trace_result(
                trace_id,
                success=False,
                error=str(e)
            )

    async def poll_and_execute_traces(self):
        """Poll for pending traces and execute them."""
        try:
            # Get pending traces
            traces = await self.api_client.get_pending_traces()

            for trace in traces:
                # Execute trace
                await self.execute_trace(trace)

                # Small delay between traces to respect throttle
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error polling traces: {e}")

    async def _poll_for_trace_response(self, tag: int, max_attempts: int = 20):
        """
        Poll for trace response messages.

        Args:
            tag: The trace tag to look for
            max_attempts: Maximum number of polling attempts
        """
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(0.5)  # Poll every 500ms

                # Try to fetch a message
                msg_result = await self.meshcore.commands.get_msg()

                if hasattr(msg_result, 'type') and msg_result.type.name != 'ERROR':
                    logger.info(f"Retrieved message while polling for trace {tag}: {msg_result}")

                    # Check if this message contains trace response data
                    if hasattr(msg_result, 'payload') and msg_result.payload:
                        payload = msg_result.payload
                        # TODO: Parse the payload to extract path and tag
                        # For now, just log it
                        logger.info(f"Message payload: {payload}")

            except Exception as e:
                logger.debug(f"Error polling for messages: {e}")

    def on_trace_response(self, tag: int, path: list, snr_values: list):
        """
        Called when a trace response is received.

        Args:
            tag: The trace tag that was used in the request
            path: List of node hashes in the path
            snr_values: List of SNR values for each hop
        """
        logger.info(f"Received trace response for tag {tag}: path={path}, SNR={snr_values}")

        # Check if we have a pending trace with this tag
        future = self.pending_traces.get(tag)
        if future and not future.done():
            # Deliver the response to the waiting coroutine
            future.set_result({
                "path": path,
                "snr_values": snr_values
            })
        else:
            logger.warning(f"Received trace response for unknown or expired tag {tag}")
