"""Main CDK Stack for Nova Sonic Healthcare Call Center."""

import os
from aws_cdk import (
    Stack,
    CfnOutput,
)
from cdk_nag import NagSuppressions
from constructs import Construct

from cdk_constructs.dynamodb_construct import DynamoDBConstruct
from cdk_constructs.cognito_construct import CognitoConstruct
from cdk_constructs.sns_construct import SNSConstruct
from cdk_constructs.agentcore_construct import AgentCoreConstruct


class HealthcareStack(Stack):
    """Main stack for Nova Sonic Healthcare Call Center infrastructure."""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        """
        Create all infrastructure for the Healthcare Call Center.

        Components created:
        - DynamoDB tables (Patients, Appointments, AvailableSlots)
        - Cognito User Pool and Identity Pool
        - SNS topic for escalations
        - AgentCore Runtime with BidiAgent

        Note: Run `python scripts/seed_data.py` after deployment to seed sample data.
        """
        super().__init__(scope, id, **kwargs)

        # Create DynamoDB tables
        dynamodb = DynamoDBConstruct(self, "DynamoDB")

        # Get escalation email from context (optional)
        escalation_email = self.node.try_get_context("escalation_email")

        # Create SNS topic with optional email subscription
        sns = SNSConstruct(
            self,
            "SNS",
            escalation_email=escalation_email,
        )

        # Create Cognito (without AgentCore ARN initially)
        cognito = CognitoConstruct(self, "Cognito")

        # Get backend code path relative to infrastructure directory
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        backend_path = os.path.abspath(backend_path)

        # Create AgentCore Runtime with BidiAgent (uses IAM/SigV4 authentication)
        agentcore = AgentCoreConstruct(
            self,
            "AgentCore",
            backend_code_path=backend_path,
            dynamodb_table_arns=dynamodb.table_arns,
            dynamodb_table_names=dynamodb.table_names,
            sns_topic_arn=sns.topic_arn,
        )

        # Grant Cognito authenticated users permission to invoke AgentCore
        cognito.grant_invoke_agentcore(agentcore.runtime_arn)

        # CDK Nag: suppress IAM5 on authenticated role — runtime-endpoint/* wildcard
        # is required because the endpoint name is dynamically assigned by AgentCore
        NagSuppressions.add_resource_suppressions(
            cognito.authenticated_role,
            [{"id": "AwsSolutions-IAM5", "reason": "runtime-endpoint/* wildcard required — endpoint name dynamically assigned by AgentCore"}],
            apply_to_children=True,
        )

        # Grant Cognito authenticated users read access to Patients table
        cognito.grant_dynamodb_read([dynamodb.patients_table.table_arn])

        # Stack Outputs for Frontend Configuration
        CfnOutput(
            self,
            "AwsRegion",
            value=self.region,
            description="AWS Region",
            export_name="NovaHealthcare-AwsRegion",
        )

        CfnOutput(
            self,
            "AgentCoreRuntimeArn",
            value=agentcore.runtime_arn,
            description="AgentCore Runtime ARN for frontend WebSocket connection",
            export_name="NovaHealthcare-AgentCoreRuntimeArn",
        )

        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=cognito.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name="NovaHealthcare-UserPoolId",
        )

        CfnOutput(
            self,
            "CognitoClientId",
            value=cognito.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name="NovaHealthcare-ClientId",
        )

        CfnOutput(
            self,
            "CognitoIdentityPoolId",
            value=cognito.identity_pool.ref,
            description="Cognito Identity Pool ID",
            export_name="NovaHealthcare-IdentityPoolId",
        )

        CfnOutput(
            self,
            "EscalationTopicArn",
            value=sns.topic_arn,
            description="SNS Escalation Topic ARN",
            export_name="NovaHealthcare-EscalationTopicArn",
        )

        CfnOutput(
            self,
            "AgentCoreExecutionRoleArn",
            value=agentcore.execution_role_arn,
            description="AgentCore Execution Role ARN",
            export_name="NovaHealthcare-AgentCoreRoleArn",
        )

        CfnOutput(
            self,
            "PatientsTableName",
            value=dynamodb.patients_table.table_name,
            description="Patients DynamoDB Table Name",
            export_name="NovaHealthcare-PatientsTable",
        )

        CfnOutput(
            self,
            "AppointmentsTableName",
            value=dynamodb.appointments_table.table_name,
            description="Appointments DynamoDB Table Name",
            export_name="NovaHealthcare-AppointmentsTable",
        )

        CfnOutput(
            self,
            "AvailableSlotsTableName",
            value=dynamodb.available_slots_table.table_name,
            description="AvailableSlots DynamoDB Table Name",
            export_name="NovaHealthcare-AvailableSlotsTable",
        )
