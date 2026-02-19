"""Patient Authentication Tool.

Verifies patient identity using name and SSN and retrieves appointment details.
"""

import logging
from dataclasses import dataclass, asdict
from typing import Dict, Optional

from strands import tool

from clients.dynamodb_client import DynamoDBClient

logger = logging.getLogger(__name__)

# Singleton client instance
_db_client: Optional[DynamoDBClient] = None

# Per-patient failed attempt tracking (module-level, resets per container/process)
MAX_ATTEMPTS = 3
_failed_attempts: Dict[str, int] = {}


def get_db_client() -> DynamoDBClient:
    """Get or create DynamoDB client singleton."""
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


@dataclass
class AuthenticationResult:
    """Result of patient authentication attempt."""

    success: bool
    patient_id: Optional[str]
    patient_name: Optional[str]
    appointment_id: Optional[str]
    appointment_details: Optional[dict]
    message: str


@tool
def authenticate_patient(first_name: str, last_name: str, ssn_last_four: str) -> dict:
    """Verify a patient's identity when they provide their name and last 4 digits of their SSN.

    Use this tool at the start of every call to authenticate the patient before
    discussing any appointment details. Returns patient information and their
    upcoming appointment details on successful authentication.

    Args:
        first_name: Patient's first name
        last_name: Patient's last name
        ssn_last_four: Last 4 digits of patient's SSN (must be exactly 4 digits)

    Returns:
        Dictionary with authentication result including patient and appointment details
    """
    logger.info("Authenticating patient: %s %s", first_name, last_name)

    # Rate limiting: track failed attempts per name combination
    attempt_key = f"{first_name.strip().lower()}:{last_name.strip().lower()}"

    if _failed_attempts.get(attempt_key, 0) >= MAX_ATTEMPTS:
        logger.warning(
            "Authentication locked out for %s %s (max attempts reached)",
            first_name,
            last_name,
        )
        result = AuthenticationResult(
            success=False,
            patient_id=None,
            patient_name=None,
            appointment_id=None,
            appointment_details=None,
            message="Maximum authentication attempts reached. For your security, please contact our office directly for assistance.",
        )
        return asdict(result)

    db = get_db_client()

    # Look up patient
    patient = db.get_patient(first_name, last_name, ssn_last_four)

    if not patient:
        _failed_attempts[attempt_key] = _failed_attempts.get(attempt_key, 0) + 1
        remaining = MAX_ATTEMPTS - _failed_attempts[attempt_key]
        logger.warning(
            "Authentication failed for %s %s (attempt %d/%d)",
            first_name,
            last_name,
            _failed_attempts[attempt_key],
            MAX_ATTEMPTS,
        )
        result = AuthenticationResult(
            success=False,
            patient_id=None,
            patient_name=None,
            appointment_id=None,
            appointment_details=None,
            message=f"Authentication failed. No patient found matching the provided information. You have {remaining} attempt(s) remaining.",
        )
        return asdict(result)

    # Clear failed attempts on successful lookup
    _failed_attempts.pop(attempt_key, None)

    patient_id = patient.get("PatientId")
    patient_name = (
        f"{patient.get('FirstName', '')} {patient.get('LastName', '')}".strip()
    )

    # Get patient's upcoming appointments
    appointments = db.get_patient_appointments(patient_id)

    # Filter to only scheduled/confirmed appointments
    valid_statuses = ["Scheduled", "Confirmed", "Rescheduled"]
    upcoming = [a for a in appointments if a.get("Status") in valid_statuses]

    if not upcoming:
        result = AuthenticationResult(
            success=True,
            patient_id=patient_id,
            patient_name=patient_name,
            appointment_id=None,
            appointment_details=None,
            message=f"Welcome {patient_name}! You have been verified, but you don't have any upcoming appointments scheduled.",
        )
        return asdict(result)

    # Get the first upcoming appointment
    appointment = upcoming[0]
    appointment_id = appointment.get("AppointmentId")

    appointment_details = {
        "date": appointment.get("AppointmentDate"),
        "time": appointment.get("AppointmentTime"),
        "provider": appointment.get("ProviderName"),
        "status": appointment.get("Status"),
        "reason": appointment.get("Reason"),
    }

    result = AuthenticationResult(
        success=True,
        patient_id=patient_id,
        patient_name=patient_name,
        appointment_id=appointment_id,
        appointment_details=appointment_details,
        message=f"Welcome {patient_name}! I found your appointment on {appointment_details['date']} at {appointment_details['time']} with {appointment_details['provider']}.",
    )

    logger.info("Authentication successful for patient %s", patient_id)
    return asdict(result)
