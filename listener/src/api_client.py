"""API client for communicating with Processing component."""
import httpx
import logging
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from .config import settings

logger = logging.getLogger(__name__)


class ProcessingAPIClient:
    """Client for sending data to Processing component."""

    def __init__(self):
        self.base_url = settings.processing_url.rstrip("/")
        self.api_key = settings.listener_api_key
        self.listener_id = settings.listener_id
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_data(self, data_type: str, data: Dict[str, Any]):
        """
        Send data to Processing component.

        Args:
            data_type: Type of data ("path", "contact", "trace_result")
            data: Data payload
        """
        try:
            # Build GPS coordinates if available
            gps = None
            if settings.gps_lat is not None and settings.gps_lon is not None:
                gps = {
                    "lat": settings.gps_lat,
                    "lon": settings.gps_lon
                }

            # Build submission payload
            payload = {
                "listener_id": str(self.listener_id),
                "listener_gps": gps,
                "timestamp": datetime.utcnow().isoformat(),
                "data_type": data_type,
                "data": data
            }

            # Send to Processing API
            url = f"{self.base_url}/api/v1/listener/data"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )

            if response.status_code == 201:
                logger.debug(f"Successfully sent {data_type} data to Processing")
            else:
                logger.error(
                    f"Failed to send data: {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"Error sending data to Processing: {e}")

    async def get_pending_traces(self):
        """Get pending trace commands from Processing."""
        try:
            url = f"{self.base_url}/api/v1/listener/traces/pending"
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            response = await self.client.get(url, headers=headers)

            if response.status_code == 200:
                traces = response.json()
                logger.debug(f"Retrieved {len(traces)} pending traces")
                return traces
            else:
                logger.error(
                    f"Failed to get pending traces: {response.status_code} - {response.text}"
                )
                return []

        except Exception as e:
            logger.error(f"Error getting pending traces: {e}")
            return []

    async def claim_trace(self, trace_id: str):
        """Claim a trace for execution."""
        try:
            url = f"{self.base_url}/api/v1/listener/traces/{trace_id}/claim"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Send listener_id as query parameter, not in body
            response = await self.client.post(
                url,
                params={"listener_id": str(self.listener_id)},
                headers=headers
            )

            if response.status_code == 200:
                logger.info(f"Successfully claimed trace {trace_id}")
                return True
            else:
                logger.error(
                    f"Failed to claim trace: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error claiming trace: {e}")
            return False

    async def submit_trace_result(
        self,
        trace_id: str,
        success: bool,
        path: list = None,
        snr_values: list = None,
        formatted_path: str = None,
        error: str = None
    ):
        """Submit trace command result."""
        try:
            url = f"{self.base_url}/api/v1/listener/traces/{trace_id}/result"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "trace_id": trace_id,
                "success": success,
                "path": path,
                "snr_values": snr_values,
                "formatted_path": formatted_path,
                "error": error
            }

            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                logger.info(f"Successfully submitted trace result for {trace_id}")
            else:
                logger.error(
                    f"Failed to submit trace result: {response.status_code} - {response.text}"
                )

        except Exception as e:
            logger.error(f"Error submitting trace result: {e}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
