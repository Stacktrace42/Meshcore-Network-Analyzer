"""Contact management for repeaters."""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ContactManager:
    """Manages repeater contacts from the MeshCore device."""

    def __init__(self, data_callback):
        """
        Initialize contact manager.

        Args:
            data_callback: Function to call with contact data
        """
        self.data_callback = data_callback
        self.contacts = {}
        self.repeater_snr = {}  # Maps hash -> best SNR observed

    async def fetch_contacts(self, meshcore):
        """
        Fetch all contacts from the device and filter for repeaters.

        Sends repeater contacts to Processing API.
        """
        try:
            logger.info("Fetching contacts from device")

            # Use commands.get_contacts() for meshcore 2.2.5+
            result = await meshcore.commands.get_contacts()

            # Check for errors
            if hasattr(result, 'type') and result.type.name == "ERROR":
                logger.error(f"Error fetching contacts: {result.payload}")
                return

            # The payload IS the contacts (not nested under a key)
            contacts = result.payload if result and hasattr(result, 'payload') else None

            if not contacts:
                logger.info("No contacts found on device")
                return

            # Handle both list and dict formats
            contact_list = []
            if isinstance(contacts, dict):
                # If dict, could be key->contact mapping
                contact_list = list(contacts.values()) if contacts else []
                logger.info(f"Fetched {len(contact_list)} contacts (dict format)")
            elif isinstance(contacts, list):
                contact_list = contacts
                logger.info(f"Fetched {len(contact_list)} contacts (list format)")
            else:
                logger.warning(f"Unexpected contacts format: {type(contacts)}")
                return

            for contact in contact_list:
                await self._process_contact(contact)

        except Exception as e:
            logger.error(f"Error fetching contacts: {e}", exc_info=True)

    async def _process_contact(self, contact: Dict[str, Any]):
        """
        Process a single contact and send to Processing if it's a repeater.

        Args:
            contact: Contact data from MeshCore
        """
        try:
            # Log the contact structure for debugging
            logger.debug(f"Processing contact: {contact}")

            # Extract public key (could be "public_key" or "pubkey")
            public_key = contact.get("public_key") or contact.get("pubkey", b"")
            if isinstance(public_key, bytes):
                public_key_hex = public_key.hex()
            elif isinstance(public_key, str):
                public_key_hex = public_key
            else:
                logger.warning(f"Invalid public key type: {type(public_key)}")
                return

            # First byte is the hash
            if len(public_key_hex) >= 2:
                hash_val = public_key_hex[:2]
            else:
                logger.warning(f"Invalid public key length: {public_key_hex}")
                return

            # Extract name (could be "adv_name", "name", or missing)
            name = contact.get("adv_name") or contact.get("name", "")

            # Extract contact type and check if repeater
            contact_type = contact.get("type", 0)
            adv_type = contact.get("adv_type", 0)

            # Type 2 = repeater, or adv_type indicates repeater
            # For now, send all contacts and let Processing decide
            is_repeater = (contact_type == 2) or (adv_type == 2)

            # Extract GPS if available
            # Could be "lat"/"lon" or "adv_lat"/"adv_lon"
            gps_lat = contact.get("lat") or contact.get("adv_lat")
            gps_lon = contact.get("lon") or contact.get("adv_lon")

            # Convert GPS if they're integers (stored as lat*1000000)
            if gps_lat and isinstance(gps_lat, int):
                gps_lat = gps_lat / 1000000.0
            if gps_lon and isinstance(gps_lon, int):
                gps_lon = gps_lon / 1000000.0

            # Send to Processing
            data = {
                "public_key": public_key_hex,
                "hash": f"0x{hash_val}",
                "name": name,
                "gps_lat": gps_lat,
                "gps_lon": gps_lon,
                "is_repeater": is_repeater
            }

            await self.data_callback("contact", data)

            # Cache contact
            self.contacts[hash_val] = data

            logger.info(f"Processed contact: {name or 'unnamed'} ({hash_val}) - repeater: {is_repeater}")

        except Exception as e:
            logger.error(f"Error processing contact: {e}", exc_info=True)

    def get_repeater_by_hash(self, hash_val: str) -> Dict[str, Any]:
        """Get cached repeater by hash."""
        return self.contacts.get(hash_val.replace("0x", ""))

    def get_all_repeaters(self) -> List[Dict[str, Any]]:
        """Get all cached repeaters."""
        return list(self.contacts.values())
