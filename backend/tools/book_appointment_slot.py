"""Book Appointment Slot Tool.

Books a selected time slot for appointment rescheduling.
"""

import logging
from dataclasses import dataclass, asdict
from typing import Optional

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
class BookingResult:
    """Result of slot booking."""

    success: bool
    message: str
    new_appointment_details: Optional[dict]


@tool
def book_appointment_slot(appointment_id: str, slot_id: str) -> dict:
    """Book a selected time slot to reschedule an appointment.

    Use this tool after the patient has selected a specific time slot from
    the available options. Books the selected slot and updates the appointment
    record with the new date and time.

    Args:
        appointment_id: ID of the appointment to reschedule
        slot_id: ID of the selected time slot to book

    Returns:
        Dictionary with booking result and new appointment details
    """
    logger.info("Booking slot %s for appointment %s", slot_id, appointment_id)

    db = get_db_client()

    # Verify the appointment exists
    appointment = db.get_appointment(appointment_id)

    if not appointment:
        result = BookingResult(
            success=False,
            message="Appointment not found. Please verify the appointment ID.",
            new_appointment_details=None,
        )
        logger.warning("Appointment not found: %s", appointment_id)
        return asdict(result)

    # Book the slot (this also updates the appointment)
    booking_result = db.book_slot(slot_id, appointment_id)

    if not booking_result.get("success"):
        result = BookingResult(
            success=False,
            message=booking_result.get(
                "message", "Failed to book the selected slot. Please try again."
            ),
            new_appointment_details=None,
        )
        return asdict(result)

    # Get the updated appointment details
    new_details = booking_result.get("appointment_details", {})

    new_appointment_details = {
        "date": new_details.get("date"),
        "time": new_details.get("time"),
        "provider": new_details.get("provider_name"),
        "status": "Rescheduled",
    }

    result = BookingResult(
        success=True,
        message=f"Your appointment has been rescheduled to {new_appointment_details['date']} at {new_appointment_details['time']} with {new_appointment_details['provider']}.",
        new_appointment_details=new_appointment_details,
    )

    logger.info("Appointment %s rescheduled to slot %s", appointment_id, slot_id)
    return asdict(result)
