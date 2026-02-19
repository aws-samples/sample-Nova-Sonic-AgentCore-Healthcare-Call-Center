"""DynamoDB Client for Healthcare Data Operations.

Provides methods for patient authentication, appointment management,
and slot availability queries.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """Client for DynamoDB operations for healthcare appointment data."""

    def __init__(self, region: Optional[str] = None):
        """Initialize the DynamoDB client.

        Args:
            region: AWS region name. Defaults to AWS_REGION env var or 'us-east-1'.
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)

        # Table names from environment variables
        patients_table_name = os.environ.get("PATIENTS_TABLE", "Patients")
        appointments_table_name = os.environ.get("APPOINTMENTS_TABLE", "Appointments")
        available_slots_table_name = os.environ.get(
            "AVAILABLE_SLOTS_TABLE", "AvailableSlots"
        )

        self.patients_table = self.dynamodb.Table(patients_table_name)
        self.appointments_table = self.dynamodb.Table(appointments_table_name)
        self.available_slots_table = self.dynamodb.Table(available_slots_table_name)

        logger.info("DynamoDB client initialized in region %s", self.region)

    def get_patient(
        self, first_name: str, last_name: str, ssn_last_four: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve patient by authentication credentials.

        Args:
            first_name: Patient's first name
            last_name: Patient's last name
            ssn_last_four: Last 4 digits of SSN

        Returns:
            Patient record or None if not found
        """
        try:
            # Normalize names to title case
            normalized_first = self._normalize_name(first_name)
            normalized_last = self._normalize_name(last_name)

            logger.info("Looking up patient by name")

            # Query using the GSI for FirstName + LastName, then filter by SSN
            response = self.patients_table.query(
                IndexName="FirstLastSSNIndex",
                KeyConditionExpression="#fname = :fname AND #lname = :lname",
                FilterExpression="#ssn = :ssn",
                ExpressionAttributeNames={
                    "#fname": "FirstName",
                    "#lname": "LastName",
                    "#ssn": "SSNLast4",
                },
                ExpressionAttributeValues={
                    ":fname": normalized_first,
                    ":lname": normalized_last,
                    ":ssn": ssn_last_four,
                },
            )

            items = response.get("Items", [])
            if not items:
                logger.warning("No patient found matching provided credentials")
                return None

            patient = items[0]
            logger.info("Patient found successfully")
            return patient

        except ClientError as e:
            logger.error("Error looking up patient: %s", e)
            return None

    def get_appointment(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve appointment by ID.

        Args:
            appointment_id: Appointment ID

        Returns:
            Appointment record or None if not found
        """
        try:
            response = self.appointments_table.get_item(
                Key={"AppointmentId": appointment_id}
            )
            appointment = response.get("Item")

            if appointment:
                logger.info("Appointment retrieved successfully")
            else:
                logger.warning("Appointment not found")

            return appointment

        except ClientError as e:
            logger.error("Error retrieving appointment: %s", e)
            return None

    def get_patient_appointments(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieve all appointments for a patient.

        Args:
            patient_id: Patient ID

        Returns:
            List of appointment records
        """
        try:
            # Query using the PatientIndex GSI
            response = self.appointments_table.query(
                IndexName="PatientIndex",
                KeyConditionExpression="PatientId = :patient_id",
                ExpressionAttributeValues={":patient_id": patient_id},
            )

            appointments = response.get("Items", [])
            logger.info("Retrieved %d appointments for patient", len(appointments))
            return appointments

        except ClientError as e:
            logger.error("Error retrieving appointments for patient: %s", e)
            return []

    def update_appointment_status(
        self, appointment_id: str, status: str, notes: Optional[str] = None
    ) -> bool:
        """Update appointment status.

        Args:
            appointment_id: Appointment ID
            status: New status (Confirmed/Cancelled/Rescheduled/Escalated)
            notes: Optional notes to append

        Returns:
            True if update successful
        """
        try:
            update_expr = "SET #status = :status"
            expr_names = {"#status": "Status"}
            expr_values = {":status": status}

            if notes:
                update_expr += (
                    ", Notes = list_append(if_not_exists(Notes, :empty_list), :note)"
                )
                expr_values[":empty_list"] = []
                expr_values[":note"] = [
                    {"timestamp": datetime.now().isoformat(), "note": notes}
                ]

            self.appointments_table.update_item(
                Key={"AppointmentId": appointment_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )

            logger.info("Updated appointment status to %s", status)
            return True

        except ClientError as e:
            logger.error("Error updating appointment status: %s", e)
            return False

    def update_appointment_notes(self, appointment_id: str, notes: str) -> bool:
        """Append notes to appointment record.

        Args:
            appointment_id: Appointment ID
            notes: Notes to append

        Returns:
            True if update successful
        """
        try:
            self.appointments_table.update_item(
                Key={"AppointmentId": appointment_id},
                UpdateExpression="SET Notes = list_append(if_not_exists(Notes, :empty_list), :note)",
                ExpressionAttributeValues={
                    ":empty_list": [],
                    ":note": [{"timestamp": datetime.now().isoformat(), "note": notes}],
                },
            )

            logger.info("Added notes to appointment")
            return True

        except ClientError as e:
            logger.error("Error adding notes to appointment: %s", e)
            return False

    def query_available_slots(self, provider_id: str, date: str) -> Dict[str, Any]:
        """Query available appointment slots for a provider on a date.

        Args:
            provider_id: Provider ID from original appointment
            date: Date to search (YYYY-MM-DD)

        Returns:
            Dict with success status and list of available slots
        """
        try:
            # Query using the ProviderDateIndex GSI
            response = self.available_slots_table.query(
                IndexName="ProviderDateIndex",
                KeyConditionExpression="ProviderId = :provider_id AND SlotDate = :date",
                FilterExpression="Available = :available",
                ExpressionAttributeValues={
                    ":provider_id": provider_id,
                    ":date": date,
                    ":available": True,
                },
            )

            slots = response.get("Items", [])

            # Sort by time
            slots.sort(key=lambda s: s.get("SlotTime", ""))

            # Limit to 3 slots for voice conversation
            limited_slots = slots[:3]

            logger.info("Found %d available slots for requested date", len(limited_slots))

            return {
                "success": True,
                "slots": limited_slots,
                "message": f"Found {len(limited_slots)} available slots",
            }

        except ClientError as e:
            logger.error("Error querying available slots: %s", e)
            return {
                "success": False,
                "slots": [],
                "message": f"Error querying slots: {str(e)}",
            }

    def book_slot(self, slot_id: str, appointment_id: str) -> Dict[str, Any]:
        """Book an available slot for appointment.

        Args:
            slot_id: Slot ID to book
            appointment_id: Appointment to reschedule

        Returns:
            Dict with success status and new appointment details
        """
        try:
            # Get the slot details
            slot_response = self.available_slots_table.get_item(Key={"SlotId": slot_id})
            slot = slot_response.get("Item")

            if not slot:
                return {"success": False, "message": "Slot not found"}

            if not slot.get("Available", False):
                return {"success": False, "message": "Slot is no longer available"}

            # Atomically mark slot as unavailable (prevents double-booking)
            try:
                self.available_slots_table.update_item(
                    Key={"SlotId": slot_id},
                    UpdateExpression="SET Available = :unavailable",
                    ConditionExpression="Available = :available",
                    ExpressionAttributeValues={
                        ":unavailable": False,
                        ":available": True,
                    },
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return {"success": False, "message": "Slot is no longer available"}
                raise

            # Update the appointment with new slot details
            self.appointments_table.update_item(
                Key={"AppointmentId": appointment_id},
                UpdateExpression="SET AppointmentDate = :date, AppointmentTime = :time, #status = :status",
                ExpressionAttributeNames={"#status": "Status"},
                ExpressionAttributeValues={
                    ":date": slot.get("SlotDate"),
                    ":time": slot.get("SlotTime"),
                    ":status": "Rescheduled",
                },
            )

            logger.info("Slot booked successfully for appointment")

            return {
                "success": True,
                "appointment_details": {
                    "date": slot.get("SlotDate"),
                    "time": slot.get("SlotTime"),
                    "provider_name": slot.get("ProviderName"),
                },
            }

        except ClientError as e:
            logger.error("Error booking slot: %s", e)
            return {"success": False, "message": f"Error booking slot: {str(e)}"}

    def _normalize_name(self, name: str) -> str:
        """Normalize patient name to Title Case.

        Args:
            name: Raw patient name

        Returns:
            Normalized patient name
        """
        if not name:
            return name

        words = name.split()
        normalized_words = []

        for word in words:
            if not word:
                continue

            # Handle O'Brien style names
            if "'" in word:
                parts = word.split("'")
                normalized_word = parts[0].capitalize() + "'" + parts[1].capitalize()
                normalized_words.append(normalized_word)
                continue

            # Handle McDonald style names
            if word.lower().startswith("mc") and len(word) > 2:
                normalized_word = "Mc" + word[2].upper() + word[3:].lower()
                normalized_words.append(normalized_word)
                continue

            # Default case
            normalized_words.append(word.capitalize())

        return " ".join(normalized_words)
