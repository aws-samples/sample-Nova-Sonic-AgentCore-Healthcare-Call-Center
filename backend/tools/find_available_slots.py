"""Find Available Appointment Slots Tool.

Searches for available appointment slots for rescheduling.
"""

import logging
from dataclasses import dataclass, asdict
from typing import List, Optional

from strands import tool

from clients.dynamodb_client import DynamoDBClient

logger = logging.getLogger(__name__)

# Singleton client instance
_db_client: Optional[DynamoDBClient] = None


def get_db_client() -> DynamoDBClient:
    """Get or create DynamoDB client singleton."""
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


@dataclass
class TimeSlot:
    """An available appointment time slot."""

    slot_id: str
    date: str
    time: str
    provider_name: str


@dataclass
class AvailableSlotsResult:
    """Result of available slots search."""

    success: bool
    message: str
    slots: Optional[List[dict]]


@tool
def find_available_slots(appointment_id: str, preferred_date: str) -> dict:
    """Search for available appointment slots for rescheduling.

    Use this tool when a patient wants to reschedule their appointment.
    Takes the patient's preferred date and returns available slots for that day.
    Present the options to the patient and let them choose.

    Args:
        appointment_id: ID of the appointment to reschedule (used to find the same provider)
        preferred_date: Date in YYYY-MM-DD format. Convert the patient's natural language
            date preference (e.g., "next Friday", "March 5th") to this format yourself.
            NEVER ask the patient to provide a specific date format on a voice call.

    Returns:
        Dictionary with list of available time slots for the date
    """
    logger.info(
        "Finding available slots for appointment %s on %s",
        appointment_id,
        preferred_date,
    )

    db = get_db_client()

    # Get the current appointment to find the provider
    appointment = db.get_appointment(appointment_id)

    if not appointment:
        result = AvailableSlotsResult(
            success=False,
            message="Appointment not found. Please verify the appointment ID.",
            slots=None,
        )
        logger.warning("Appointment not found: %s", appointment_id)
        return asdict(result)

    provider_id = appointment.get("ProviderId")
    provider_name = appointment.get("ProviderName")

    # Query available slots for the provider on the preferred date
    slots_result = db.query_available_slots(
        provider_id=provider_id, date=preferred_date
    )

    if not slots_result.get("success"):
        result = AvailableSlotsResult(
            success=False,
            message=slots_result.get("message", "Error searching for available slots."),
            slots=None,
        )
        return asdict(result)

    available_slots = slots_result.get("slots", [])

    if not available_slots:
        result = AvailableSlotsResult(
            success=True,
            message=f"No available slots found with {provider_name} on {preferred_date}. Would you like to try a different date?",
            slots=[],
        )
        return asdict(result)

    # Format slots for presentation
    formatted_slots = []
    for slot in available_slots:
        formatted_slot = {
            "slot_id": slot.get("SlotId"),
            "date": slot.get("SlotDate"),
            "time": slot.get("SlotTime"),
            "provider_name": slot.get("ProviderName", provider_name),
        }
        formatted_slots.append(formatted_slot)

    # Create readable message
    slot_descriptions = [f"{s['time']} on {s['date']}" for s in formatted_slots]
    slots_text = ", ".join(slot_descriptions)

    result = AvailableSlotsResult(
        success=True,
        message=f"I found {len(formatted_slots)} available slots with {provider_name}: {slots_text}. Which time works best for you?",
        slots=formatted_slots,
    )

    logger.info("Found %d available slots for %s", len(formatted_slots), preferred_date)
    return asdict(result)
