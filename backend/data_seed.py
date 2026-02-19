#!/usr/bin/env python3
"""Seed DynamoDB tables for Nova Sonic Healthcare Call Center.

This script populates the CDK-created DynamoDB tables with sample data.
Run this after CDK deployment to set up test data.

Usage:
    python data_seed.py [--region us-east-1]
"""

import boto3
import os
import uuid
import random
import argparse
import datetime

# Table names (must match CDK-deployed table names)
PATIENTS_TABLE = os.environ.get("PATIENTS_TABLE", "nova-healthcare-patients")
APPOINTMENTS_TABLE = os.environ.get(
    "APPOINTMENTS_TABLE", "nova-healthcare-appointments"
)
AVAILABLE_SLOTS_TABLE = os.environ.get("AVAILABLE_SLOTS_TABLE", "nova-healthcare-slots")

# Configure the region
region = os.environ.get("AWS_REGION", "us-east-1")

# Create DynamoDB resource
dynamodb = boto3.resource("dynamodb", region_name=region)

# Sample data - Providers
PROVIDERS = [
    {"ProviderId": "DR-001", "ProviderName": "Dr. Sarah Johnson"},
    {"ProviderId": "DR-002", "ProviderName": "Dr. Michael Chen"},
    {"ProviderId": "DR-003", "ProviderName": "Dr. Emily Williams"},
    {"ProviderId": "DR-004", "ProviderName": "Dr. James Brown"},
    {"ProviderId": "DR-005", "ProviderName": "Dr. Lisa Davis"},
]

# Sample appointment types
APPOINTMENT_TYPES = [
    "Annual Checkup",
    "Follow-up Visit",
    "Consultation",
    "Routine Visit",
]

# Sample patient data
PATIENTS = [
    {
        "FirstName": "John",
        "LastName": "Smith",
        "SSNLast4": "1234",
        "Phone": "+15551234567",
        "Email": "john.smith@email.com",
    },
    {
        "FirstName": "Jane",
        "LastName": "Doe",
        "SSNLast4": "5678",
        "Phone": "+15559876543",
        "Email": "jane.doe@email.com",
    },
    {
        "FirstName": "Michael",
        "LastName": "Johnson",
        "SSNLast4": "9012",
        "Phone": "+15551112222",
        "Email": "michael.johnson@email.com",
    },
    {
        "FirstName": "Sarah",
        "LastName": "Wilson",
        "SSNLast4": "3456",
        "Phone": "+15553334444",
        "Email": "sarah.wilson@email.com",
    },
    {
        "FirstName": "Robert",
        "LastName": "Brown",
        "SSNLast4": "7890",
        "Phone": "+15555556666",
        "Email": "robert.brown@email.com",
    },
    {
        "FirstName": "Emily",
        "LastName": "Davis",
        "SSNLast4": "2345",
        "Phone": "+15557778888",
        "Email": "emily.davis@email.com",
    },
]


def generate_patient_id():
    """Generate a unique PatientId."""
    return f"P-{str(uuid.uuid4())[:8]}"


def generate_appointment_id():
    """Generate a unique AppointmentId."""
    return f"APT-{str(uuid.uuid4())[:8]}"


def generate_slot_id():
    """Generate a unique SlotId."""
    return f"SLOT-{str(uuid.uuid4())[:8]}"


def generate_future_date(days_ahead_min=1, days_ahead_max=14):
    """Generate a random date within the specified range."""
    today = datetime.date.today()
    random_days = random.randint(days_ahead_min, days_ahead_max)  # nosec B311
    future_date = today + datetime.timedelta(days=random_days)
    return future_date.strftime("%Y-%m-%d")


def generate_time_slot():
    """Generate a random appointment time in 30-minute increments."""
    hour = random.randint(9, 16)  # nosec B311
    minute = random.choice([0, 30])  # nosec B311
    am_pm = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {am_pm}"


def clear_table(table_name):
    """Clear all items from a table."""
    try:
        table = dynamodb.Table(table_name)
        scan = table.scan()
        items = scan.get("Items", [])

        if not items:
            print("  Table is already empty")
            return True

        # Get key schema
        key_schema = table.key_schema
        key_names = [k["AttributeName"] for k in key_schema]

        with table.batch_writer() as batch:
            for item in items:
                key = {k: item[k] for k in key_names}
                batch.delete_item(Key=key)

        print(f"  Cleared {len(items)} items")
        return True
    except Exception as e:
        print(f"  Error clearing table: {e}")
        return False


def seed_patients_table():
    """Seed the Patients table with sample data."""
    print("\nSeeding patients table...")

    try:
        table = dynamodb.Table(PATIENTS_TABLE)

        # Clear existing data
        clear_table(PATIENTS_TABLE)

        patient_ids = []
        for patient in PATIENTS:
            patient_id = generate_patient_id()
            patient_ids.append(
                {
                    "PatientId": patient_id,
                    "FirstName": patient["FirstName"],
                    "LastName": patient["LastName"],
                }
            )

            table.put_item(
                Item={
                    "PatientId": patient_id,
                    "FirstName": patient["FirstName"],
                    "LastName": patient["LastName"],
                    "SSNLast4": patient["SSNLast4"],
                    "Phone": patient["Phone"],
                    "Email": patient["Email"],
                }
            )
            print(f"  Added patient: {patient_id}")

        print(f"  Successfully seeded {len(PATIENTS)} patients")
        return patient_ids

    except Exception as e:
        print(f"  Error seeding patients: {e}")
        return []


def seed_appointments_table(patient_records):
    """Seed the Appointments table with sample data."""
    print("\nSeeding appointments table...")

    try:
        table = dynamodb.Table(APPOINTMENTS_TABLE)

        # Clear existing data
        clear_table(APPOINTMENTS_TABLE)

        appointment_count = 0

        # Create 1-2 appointments per patient
        for patient in patient_records:
            patient_id = patient["PatientId"]
            patient_name = f"{patient['FirstName']} {patient['LastName']}"

            num_appointments = random.randint(1, 2)  # nosec B311

            for i in range(num_appointments):
                appointment_id = generate_appointment_id()
                provider = random.choice(PROVIDERS)  # nosec B311
                appointment_type = random.choice(APPOINTMENT_TYPES)  # nosec B311

                if i == 0:
                    # First appointment: guaranteed future Scheduled (3-7 days out)
                    appointment_date = generate_future_date(3, 7)
                else:
                    # Additional appointments: also Scheduled, wider range
                    appointment_date = generate_future_date(1, 14)

                appointment_time = generate_time_slot()

                item = {
                    "AppointmentId": appointment_id,
                    "PatientId": patient_id,
                    "PatientName": patient_name,
                    "ProviderId": provider["ProviderId"],
                    "ProviderName": provider["ProviderName"],
                    "AppointmentDate": appointment_date,
                    "AppointmentTime": appointment_time,
                    "AppointmentType": appointment_type,
                    "Status": "Scheduled",
                }
                print(f"  Added appointment: {appointment_id}")

                table.put_item(Item=item)
                appointment_count += 1

        print(f"  Successfully seeded {appointment_count} appointments")
        return True

    except Exception as e:
        print(f"  Error seeding appointments: {e}")
        return False


def seed_available_slots_table():
    """Seed the AvailableSlots table with sample data."""
    print("\nSeeding available slots table...")

    try:
        table = dynamodb.Table(AVAILABLE_SLOTS_TABLE)

        # Clear existing data
        clear_table(AVAILABLE_SLOTS_TABLE)

        slot_count = 0

        # Create 6 slots per provider over next 2 weeks
        for provider in PROVIDERS:
            for _ in range(6):
                slot_id = generate_slot_id()
                slot_date = generate_future_date(1, 21)
                slot_time = generate_time_slot()

                table.put_item(
                    Item={
                        "SlotId": slot_id,
                        "ProviderId": provider["ProviderId"],
                        "ProviderName": provider["ProviderName"],
                        "SlotDate": slot_date,
                        "SlotTime": slot_time,
                        "Available": True,
                    }
                )
                slot_count += 1
                print(f"  Added slot: {slot_id}")

        print(f"  Successfully seeded {slot_count} available slots")
        return True

    except Exception as e:
        print(f"  Error seeding slots: {e}")
        return False


def verify_tables_exist():
    """Verify that the CDK-created tables exist."""
    print("\nVerifying tables exist...")

    tables_ok = True
    for table_name in [PATIENTS_TABLE, APPOINTMENTS_TABLE, AVAILABLE_SLOTS_TABLE]:
        try:
            table = dynamodb.Table(table_name)
            status = table.table_status
            print(f"  Table verified: {status}")
        except Exception as e:
            print(f"  Table NOT FOUND: {e}")
            tables_ok = False

    return tables_ok


def main():
    parser = argparse.ArgumentParser(
        description="Seed DynamoDB tables for Nova Sonic Healthcare demo"
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS Region (default: us-east-1)",
    )
    args = parser.parse_args()

    global region, dynamodb
    region = args.region
    dynamodb = boto3.resource("dynamodb", region_name=region)

    print("=" * 60)
    print("Nova Sonic Healthcare - Data Seeding")
    print("=" * 60)
    print(f"Region: {region}")
    print("Tables: Patients, Appointments, AvailableSlots")

    # Verify tables exist
    if not verify_tables_exist():
        print("\nERROR: One or more tables do not exist.")
        print("Please run 'cdk deploy' first to create the tables.")
        return 1

    # Seed all tables
    patient_records = seed_patients_table()
    if patient_records:
        seed_appointments_table(patient_records)
        seed_available_slots_table()
    else:
        print("\nERROR: Failed to seed patients. Aborting.")
        return 1

    print("\n" + "=" * 60)
    print("Data seeding complete!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
