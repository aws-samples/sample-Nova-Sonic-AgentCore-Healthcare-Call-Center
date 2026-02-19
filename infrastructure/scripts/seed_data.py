#!/usr/bin/env python3
"""Data Seeder Script for Nova Sonic Healthcare.

Run this script after CDK deployment to seed DynamoDB tables with sample data.

Usage:
    python scripts/seed_data.py --profile <aws-profile> --region <region>

Example:
    python scripts/seed_data.py --profile <your-aws-profile> --region <your-deployment-region>
"""

import argparse
import uuid
import random
import datetime
import boto3


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
    {"FirstName": "John", "LastName": "Smith", "SSNLast4": "1234", "Phone": "+15551234567", "Email": "john.smith@email.com"},
    {"FirstName": "Jane", "LastName": "Doe", "SSNLast4": "5678", "Phone": "+15559876543", "Email": "jane.doe@email.com"},
    {"FirstName": "Michael", "LastName": "Johnson", "SSNLast4": "9012", "Phone": "+15551112222", "Email": "michael.johnson@email.com"},
    {"FirstName": "Sarah", "LastName": "Wilson", "SSNLast4": "3456", "Phone": "+15553334444", "Email": "sarah.wilson@email.com"},
    {"FirstName": "Robert", "LastName": "Brown", "SSNLast4": "7890", "Phone": "+15555556666", "Email": "robert.brown@email.com"},
    {"FirstName": "Emily", "LastName": "Davis", "SSNLast4": "2345", "Phone": "+15557778888", "Email": "emily.davis@email.com"},
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
    random_days = random.randint(days_ahead_min, days_ahead_max)
    future_date = today + datetime.timedelta(days=random_days)
    return future_date.strftime("%Y-%m-%d")


def generate_time_slot():
    """Generate a random appointment time in 30-minute increments."""
    hour = random.randint(9, 16)
    minute = random.choice([0, 30])
    am_pm = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {am_pm}"


def get_table_names(cfn_client, stack_name):
    """Get DynamoDB table names from CloudFormation stack outputs."""
    response = cfn_client.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]

    table_names = {}
    for output in outputs:
        if output["OutputKey"] == "PatientsTableName":
            table_names["patients"] = output["OutputValue"]
        elif output["OutputKey"] == "AppointmentsTableName":
            table_names["appointments"] = output["OutputValue"]
        elif output["OutputKey"] == "AvailableSlotsTableName":
            table_names["slots"] = output["OutputValue"]

    return table_names


def seed_patients_table(dynamodb, table_name):
    """Seed the Patients table with sample data."""
    print("Seeding patients table...")
    table = dynamodb.Table(table_name)
    patient_records = []

    for patient in PATIENTS:
        patient_id = generate_patient_id()
        patient_records.append({
            "PatientId": patient_id,
            "FirstName": patient["FirstName"],
            "LastName": patient["LastName"],
        })

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

    print(f"Successfully seeded {len(PATIENTS)} patients")
    return patient_records


def seed_appointments_table(dynamodb, table_name, patient_records):
    """Seed the Appointments table with sample data."""
    print("Seeding appointments table...")
    table = dynamodb.Table(table_name)
    appointment_count = 0

    for patient in patient_records:
        patient_id = patient["PatientId"]
        patient_name = f"{patient['FirstName']} {patient['LastName']}"
        num_appointments = random.randint(1, 2)

        for _ in range(num_appointments):
            appointment_id = generate_appointment_id()
            provider = random.choice(PROVIDERS)

            if random.random() < 0.8:
                # Scheduled appointment
                appointment_date = generate_future_date(1, 14)
                appointment_time = generate_time_slot()
                appointment_type = random.choice(APPOINTMENT_TYPES)
                status = "Scheduled"
            else:
                # Pending confirmation
                appointment_date = generate_future_date(1, 7)
                appointment_time = generate_time_slot()
                appointment_type = "Follow-up Visit"
                status = "Pending Confirmation"

            table.put_item(
                Item={
                    "AppointmentId": appointment_id,
                    "PatientId": patient_id,
                    "PatientName": patient_name,
                    "ProviderId": provider["ProviderId"],
                    "ProviderName": provider["ProviderName"],
                    "AppointmentDate": appointment_date,
                    "AppointmentTime": appointment_time,
                    "AppointmentType": appointment_type,
                    "Status": status,
                }
            )
            appointment_count += 1

    print(f"Successfully seeded {appointment_count} appointments")


def seed_available_slots_table(dynamodb, table_name):
    """Seed the AvailableSlots table with sample data."""
    print("Seeding available slots table...")
    table = dynamodb.Table(table_name)
    slot_count = 0

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

    print(f"Successfully seeded {slot_count} available slots")


def main():
    parser = argparse.ArgumentParser(description="Seed DynamoDB tables with sample healthcare data")
    parser.add_argument("--profile", required=True, help="AWS profile name")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--stack-name", default="NovaSonicHealthcareStack", help="CloudFormation stack name")
    args = parser.parse_args()

    # Create boto3 session with profile
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    cfn_client = session.client("cloudformation")
    dynamodb = session.resource("dynamodb")

    print(f"Getting table names from stack: {args.stack_name}")
    table_names = get_table_names(cfn_client, args.stack_name)

    print(f"Found {len(table_names)} tables from stack outputs")
    print()

    # Seed the tables
    patient_records = seed_patients_table(dynamodb, table_names["patients"])
    seed_appointments_table(dynamodb, table_names["appointments"], patient_records)
    seed_available_slots_table(dynamodb, table_names["slots"])

    print("\nData seeding complete!")


if __name__ == "__main__":
    main()
