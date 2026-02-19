"""DynamoDB Construct for healthcare data tables."""

from aws_cdk import (
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class DynamoDBConstruct(Construct):
    """CDK construct for healthcare DynamoDB tables."""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        """
        Create DynamoDB tables for healthcare data.

        Creates three tables:
        - Patients: Patient records with authentication lookup
        - Appointments: Appointment records with patient lookup
        - AvailableSlots: Available time slots with provider/date lookup
        """
        super().__init__(scope, id, **kwargs)

        # Patients Table
        self._patients_table = dynamodb.Table(
            self,
            "PatientsTable",
            table_name="nova-healthcare-patients",
            partition_key=dynamodb.Attribute(
                name="PatientId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI for patient authentication lookup (FirstName + LastName)
        self._patients_table.add_global_secondary_index(
            index_name="FirstLastSSNIndex",
            partition_key=dynamodb.Attribute(
                name="FirstName",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="LastName",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Appointments Table
        self._appointments_table = dynamodb.Table(
            self,
            "AppointmentsTable",
            table_name="nova-healthcare-appointments",
            partition_key=dynamodb.Attribute(
                name="AppointmentId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI for patient's appointments lookup
        self._appointments_table.add_global_secondary_index(
            index_name="PatientIndex",
            partition_key=dynamodb.Attribute(
                name="PatientId",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # AvailableSlots Table
        self._available_slots_table = dynamodb.Table(
            self,
            "AvailableSlotsTable",
            table_name="nova-healthcare-slots",
            partition_key=dynamodb.Attribute(
                name="SlotId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI for provider/date slot lookup
        self._available_slots_table.add_global_secondary_index(
            index_name="ProviderDateIndex",
            partition_key=dynamodb.Attribute(
                name="ProviderId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SlotDate",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # CDK Nag suppressions — demo tables with seeded data, PITR adds cost for no benefit
        for table in [self._patients_table, self._appointments_table, self._available_slots_table]:
            NagSuppressions.add_resource_suppressions(
                table,
                [{"id": "AwsSolutions-DDB3", "reason": "Demo project with seeded data — point-in-time recovery unnecessary"}],
            )

    @property
    def patients_table(self) -> dynamodb.Table:
        """Patients table reference."""
        return self._patients_table

    @property
    def appointments_table(self) -> dynamodb.Table:
        """Appointments table reference."""
        return self._appointments_table

    @property
    def available_slots_table(self) -> dynamodb.Table:
        """AvailableSlots table reference."""
        return self._available_slots_table

    @property
    def table_arns(self) -> list:
        """List of all table ARNs for IAM permissions."""
        return [
            self._patients_table.table_arn,
            self._appointments_table.table_arn,
            self._available_slots_table.table_arn,
        ]

    @property
    def table_names(self) -> dict:
        """Dictionary of table names for environment variables."""
        return {
            "patients": self._patients_table.table_name,
            "appointments": self._appointments_table.table_name,
            "slots": self._available_slots_table.table_name,
        }
