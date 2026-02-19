"""Appointment Confirmation Tool.

Confirms a patient's upcoming appointment.
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
class ConfirmationResult:
    """Result of appointment confirmation."""

    success: bool
    message: str
    appointment_details: Optional[dict]


@tool
def confirm_appointment(appointment_id: str) -> dict:
    """Confirm a patient's upcoming appointment.

    Use this tool when the patient wants to confirm their upcoming appointment.
    Updates the appointment status to 'Confirmed' and returns confirmation details.

    Args:
        appointment_id: ID of the appointment to confirm

    Returns:
        Dictionary with confirmation result and updated appointment details
    """
    logger.info("Confirming appointment: %s", appointment_id)

    db = get_db_client()

    # Get current appointment
    appointment = db.get_appointment(appointment_id)

    if not appointment:
        result = ConfirmationResult(
            success=False,
            message="Appointment not found. Please verify the appointment ID.",
            appointment_details=None,
        )
        logger.warning("Appointment not found: %s", appointment_id)
        return asdict(result)

    current_status = appointment.get("Status")

    # Check if already confirmed
    if current_status == "Confirmed":
        appointment_details = {
            "date": appointment.get("AppointmentDate"),
            "time": appointment.get("AppointmentTime"),
            "provider": appointment.get("ProviderName"),
            "status": "Confirmed",
        }
        result = ConfirmationResult(
            success=True,
            message="This appointment is already confirmed.",
            appointment_details=appointment_details,
        )
        return asdict(result)

    # Check if appointment can be confirmed
    if current_status not in ["Scheduled", "Rescheduled"]:
        result = ConfirmationResult(
            success=False,
            message=f"Cannot confirm appointment with status '{current_status}'. Only scheduled or rescheduled appointments can be confirmed.",
            appointment_details=None,
        )
        return asdict(result)

    # Update status to Confirmed
    success = db.update_appointment_status(appointment_id, "Confirmed")

    if not success:
        result = ConfirmationResult(
            success=False,
            message="Failed to confirm appointment. Please try again.",
            appointment_details=None,
        )
        return asdict(result)

    appointment_details = {
        "date": appointment.get("AppointmentDate"),
        "time": appointment.get("AppointmentTime"),
        "provider": appointment.get("ProviderName"),
        "status": "Confirmed",
    }

    result = ConfirmationResult(
        success=True,
        message=f"Your appointment on {appointment_details['date']} at {appointment_details['time']} with {appointment_details['provider']} has been confirmed.",
        appointment_details=appointment_details,
    )

    logger.info("Appointment %s confirmed successfully", appointment_id)
    return asdict(result)
