"""Appointment Cancellation Tool.

Cancels a patient's upcoming appointment.
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
class CancellationResult:
    """Result of appointment cancellation."""

    success: bool
    message: str


@tool
def cancel_appointment(appointment_id: str, reason: Optional[str] = None) -> dict:
    """Cancel a patient's upcoming appointment.

    Use this tool when the patient wants to cancel their upcoming appointment.
    Optionally collects a cancellation reason. Updates the appointment status
    to 'Cancelled'.

    Args:
        appointment_id: ID of the appointment to cancel
        reason: Optional reason for cancellation (for record-keeping)

    Returns:
        Dictionary with cancellation result
    """
    logger.info("Cancelling appointment: %s, reason: %s", appointment_id, reason)

    db = get_db_client()

    # Get current appointment
    appointment = db.get_appointment(appointment_id)

    if not appointment:
        result = CancellationResult(
            success=False,
            message="Appointment not found. Please verify the appointment ID.",
        )
        logger.warning("Appointment not found: %s", appointment_id)
        return asdict(result)

    current_status = appointment.get("Status")

    # Check if already cancelled
    if current_status == "Cancelled":
        result = CancellationResult(
            success=True, message="This appointment is already cancelled."
        )
        return asdict(result)

    # Check if appointment can be cancelled
    if current_status not in ["Scheduled", "Confirmed", "Rescheduled"]:
        result = CancellationResult(
            success=False,
            message=f"Cannot cancel appointment with status '{current_status}'.",
        )
        return asdict(result)

    # Build notes with cancellation reason
    notes = None
    if reason:
        notes = f"Cancellation reason: {reason}"

    # Update status to Cancelled
    success = db.update_appointment_status(appointment_id, "Cancelled", notes=notes)

    if not success:
        result = CancellationResult(
            success=False, message="Failed to cancel appointment. Please try again."
        )
        return asdict(result)

    appointment_date = appointment.get("AppointmentDate")
    appointment_time = appointment.get("AppointmentTime")
    provider_name = appointment.get("ProviderName")

    result = CancellationResult(
        success=True,
        message=f"Your appointment on {appointment_date} at {appointment_time} with {provider_name} has been cancelled.",
    )

    logger.info("Appointment %s cancelled successfully", appointment_id)
    return asdict(result)
