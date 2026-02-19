"""Healthcare Tools Package.

Provides 7 tools for the Nova Sonic Healthcare Call Center BidiAgent:
1. authenticate_patient - Verify patient identity
2. confirm_appointment - Confirm upcoming appointment
3. cancel_appointment - Cancel appointment
4. find_available_slots - Search for rescheduling options
5. book_appointment_slot - Book a new time slot
6. record_health_update - Record patient health concerns
7. escalate_to_agent - Transfer to live agent
"""

from tools.authenticate_patient import authenticate_patient
from tools.confirm_appointment import confirm_appointment
from tools.cancel_appointment import cancel_appointment
from tools.find_available_slots import find_available_slots
from tools.book_appointment_slot import book_appointment_slot
from tools.record_health_update import record_health_update
from tools.escalate_to_agent import escalate_to_agent


def get_all_tools() -> list:
    """Get list of all healthcare tools for BidiAgent.

    Returns:
        List of tool functions decorated with @tool
    """
    return [
        authenticate_patient,
        confirm_appointment,
        cancel_appointment,
        find_available_slots,
        book_appointment_slot,
        record_health_update,
        escalate_to_agent,
    ]


__all__ = [
    "authenticate_patient",
    "confirm_appointment",
    "cancel_appointment",
    "find_available_slots",
    "book_appointment_slot",
    "record_health_update",
    "escalate_to_agent",
    "get_all_tools",
]
