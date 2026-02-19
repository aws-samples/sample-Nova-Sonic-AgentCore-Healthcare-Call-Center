"""Escalate to Live Agent Tool.

Flags the call for follow-up by a live healthcare agent.
"""

import logging
import secrets
from dataclasses import dataclass, asdict
from typing import Optional

from strands import tool

from clients.dynamodb_client import DynamoDBClient
from clients.sns_client import SNSClient

logger = logging.getLogger(__name__)

# Singleton client instances
_db_client: Optional[DynamoDBClient] = None
_sns_client: Optional[SNSClient] = None


def get_db_client() -> DynamoDBClient:
    """Get or create DynamoDB client singleton."""
    global _db_client
    if _db_client is None:
        _db_client = DynamoDBClient()
    return _db_client


def get_sns_client() -> SNSClient:
    """Get or create SNS client singleton."""
    global _sns_client
    if _sns_client is None:
        _sns_client = SNSClient()
    return _sns_client


def generate_short_reference_number() -> str:
    """Generate a short, voice-friendly reference number (6 digits)."""
    return str(secrets.randbelow(900000) + 100000)


@dataclass
class EscalationResult:
    """Result of escalation to live agent."""

    success: bool
    message: str
    reference_number: Optional[str]


@tool
def escalate_to_agent(appointment_id: str, reason: str) -> dict:
    """Flag the call for follow-up by a live healthcare agent.

    Use this tool when:
    - The patient explicitly requests to speak with a live agent
    - Authentication fails after multiple attempts
    - The automated system cannot handle the patient's request
    - The patient has complex medical questions

    This does NOT transfer to a live agent immediately. Instead, it:
    1. Updates the appointment status to "Escalated"
    2. Sends an SNS notification to healthcare staff
    3. Returns a reference number for the patient to use when staff calls back

    Args:
        appointment_id: ID of the appointment (or "UNKNOWN" if not authenticated)
        reason: Reason for escalation

    Returns:
        Dictionary with escalation result and voice-friendly reference number
    """
    logger.info(
        "Flagging call for follow-up, appointment %s, reason: %s",
        appointment_id,
        reason,
    )

    db = get_db_client()
    sns = get_sns_client()

    # Generate short reference number for voice conversation
    reference_number = generate_short_reference_number()

    # Get patient info if we have a valid appointment
    patient_id = None
    patient_name = "Unknown Patient"

    if appointment_id and appointment_id != "UNKNOWN":
        appointment = db.get_appointment(appointment_id)
        if appointment:
            patient_id = appointment.get("PatientId")
            patient_name = appointment.get("PatientName", patient_name)

            # Update appointment status to Escalated with reference number
            db.update_appointment_status(
                appointment_id,
                "Escalated",
                notes=f"Escalation reason: {reason}. Reference: {reference_number}",
            )

    # Publish escalation notification
    try:
        message_id = sns.publish_escalation(
            appointment_id=appointment_id,
            patient_id=patient_id or "UNKNOWN",
            reason=f"{reason} (Reference: {reference_number})",
        )

        result = EscalationResult(
            success=True,
            message="I've noted your request and a healthcare representative will call you back within 24 hours. Is there anything else I can help you with before we end this call?",
            reference_number=reference_number,  # Kept internally for tracking
        )

        logger.info(
            "Escalation flagged with reference %s, SNS message ID: %s",
            reference_number,
            message_id,
        )

    except Exception as e:
        logger.error("Failed to publish escalation: %s", e)

        result = EscalationResult(
            success=False,
            message="I apologize, but I'm having trouble processing your request. Please call our main line at 1-800-555-ACME for immediate assistance.",
            reference_number=None,
        )

    return asdict(result)
