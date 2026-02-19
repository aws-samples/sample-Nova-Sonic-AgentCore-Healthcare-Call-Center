"""AgentCore Runtime Construct for BidiAgent deployment.

Uses the CDK AgentCore alpha construct to deploy the BidiAgent
as an AgentCore Runtime with Cognito authentication.
"""

from aws_cdk import aws_iam as iam
from cdk_nag import NagSuppressions
from constructs import Construct

# Import AgentCore alpha construct
import aws_cdk.aws_bedrock_agentcore_alpha as agentcore


class AgentCoreConstruct(Construct):
    """CDK construct for AgentCore Runtime deployment using alpha construct.

    This construct deploys the BidiAgent as an AgentCore Runtime with:
    - Container deployment from local Dockerfile
    - Cognito User Pool authentication
    - IAM permissions for DynamoDB, SNS, and Bedrock
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        backend_code_path: str,
        dynamodb_table_arns: list,
        dynamodb_table_names: dict,
        sns_topic_arn: str,
        **kwargs
    ) -> None:
        """
        Create AgentCore Runtime for BidiAgent.

        Args:
            scope: CDK scope
            id: Construct ID
            backend_code_path: Path to BidiAgent code directory (with Dockerfile)
            dynamodb_table_arns: DynamoDB table ARNs for data access
            dynamodb_table_names: Dict with table name keys (patients, appointments, slots)
            sns_topic_arn: SNS topic ARN for escalations
        """
        super().__init__(scope, id, **kwargs)

        self._backend_code_path = backend_code_path
        self._dynamodb_table_arns = dynamodb_table_arns
        self._sns_topic_arn = sns_topic_arn

        # Create AgentCore Runtime artifact from local Dockerfile
        # This builds the container and uploads to ECR
        agent_runtime_artifact = agentcore.AgentRuntimeArtifact.from_asset(
            backend_code_path
        )

        # Create the AgentCore Runtime with IAM authentication
        # Uses SigV4 signing with Cognito Identity Pool credentials
        self._runtime = agentcore.Runtime(
            self,
            "Runtime",
            runtime_name="nova_healthcare_agent",
            agent_runtime_artifact=agent_runtime_artifact,
            # Use IAM authentication (SigV4) - frontend uses Identity Pool credentials
            authorizer_configuration=agentcore.RuntimeAuthorizerConfiguration.using_iam(),
            # Environment variables for the agent
            # Bump IMAGE_VERSION to force CloudFormation to update the runtime
            # when CDK asset hash doesn't detect code changes
            environment_variables={
                "IMAGE_VERSION": "2026-02-17-v1",
                "PATIENTS_TABLE": dynamodb_table_names.get("patients", "nova-healthcare-patients"),
                "APPOINTMENTS_TABLE": dynamodb_table_names.get("appointments", "nova-healthcare-appointments"),
                "AVAILABLE_SLOTS_TABLE": dynamodb_table_names.get("slots", "nova-healthcare-slots"),
                "ESCALATION_TOPIC_ARN": sns_topic_arn,
            },
        )

        # Grant Bedrock model invocation (Nova Sonic 2)
        self._runtime.role.add_to_policy(
            iam.PolicyStatement(
                sid="InvokeNovaSonic2",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/amazon.nova-sonic-v1:0",
                    "arn:aws:bedrock:*::foundation-model/amazon.nova-2-sonic-v1:0",
                ],
            )
        )

        # Grant DynamoDB access
        self._runtime.role.add_to_policy(
            iam.PolicyStatement(
                sid="DynamoDBAccess",
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                ],
                resources=dynamodb_table_arns + [f"{arn}/index/*" for arn in dynamodb_table_arns],
            )
        )

        # Grant SNS publish for escalations
        self._runtime.role.add_to_policy(
            iam.PolicyStatement(
                sid="SNSPublish",
                actions=["sns:Publish"],
                resources=[sns_topic_arn],
            )
        )

        # CDK Nag: suppress IAM5 on execution role — Resource: * wildcards are required
        # by AWS API design for X-Ray, CloudWatch Metrics, ECR GetAuthorizationToken,
        # dynamic log groups, DynamoDB index/* GSI patterns, and Bedrock region wildcards
        NagSuppressions.add_resource_suppressions(
            self._runtime.role,
            [{"id": "AwsSolutions-IAM5", "reason": "Wildcards required by AWS API design: X-Ray, CloudWatch, ECR auth, dynamic log groups, DynamoDB GSI index/*, Bedrock cross-region model ARN"}],
            apply_to_children=True,
        )

    @property
    def runtime(self) -> agentcore.Runtime:
        """AgentCore Runtime reference."""
        return self._runtime

    @property
    def runtime_arn(self) -> str:
        """ARN of the AgentCore Runtime."""
        return self._runtime.agent_runtime_arn

    @property
    def execution_role(self) -> iam.IRole:
        """Execution role for AgentCore Runtime."""
        return self._runtime.role

    @property
    def execution_role_arn(self) -> str:
        """ARN of the execution role."""
        return self._runtime.role.role_arn
