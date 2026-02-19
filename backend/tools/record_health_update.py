"""Record Health Update Tool.

Records patient health updates or concerns for their upcoming appointment.
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
class HealthInfoResult:
    """Result of recording health update."""

    success: bool
    message: str


@tool
def record_health_update(appointment_id: str, health_update: str) -> dict:
    """Record health updates or concerns for the patient's upcoming visit.

    Use this tool to record any health updates or concerns the patient
    mentions for their upcoming visit. Stores the information in the
    appointment notes for the healthcare provider to review before the visit.

    Args:
        appointment_id: ID of the appointment
        health_update: Patient's health update or concerns to record

    Returns:
        Dictionary with result of recording the update
    """
    logger.info("Recording health update for appointment %s", appointment_id)

    db = get_db_client()

    # Verify the appointment exists
    appointment = db.get_appointment(appointment_id)

    if not appointment:
        result = HealthInfoResult(
            success=False,
            message="Appointment not found. Please verify the appointment ID.",
        )
        logger.warning("Appointment not found: %s", appointment_id)
        return asdict(result)

    # Append health update to appointment notes
    notes = f"Patient health update: {health_update}"
    success = db.update_appointment_notes(appointment_id, notes)

    if not success:
        result = HealthInfoResult(
            success=False,
            message="Failed to record your health update. Please try again.",
        )
        return asdict(result)

    result = HealthInfoResult(
        success=True,
        message="Thank you. I've recorded your health update for your provider to review before your visit.",
    )

    logger.info("Health update recorded for appointment %s", appointment_id)
    return asdict(result)
