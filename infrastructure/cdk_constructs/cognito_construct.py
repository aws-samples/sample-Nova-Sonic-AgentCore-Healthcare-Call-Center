"""Cognito Construct for user authentication."""

from aws_cdk import (
    RemovalPolicy,
    aws_cognito as cognito,
    aws_iam as iam,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class CognitoConstruct(Construct):
    """CDK construct for Cognito User Pool and Identity Pool."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        agentcore_runtime_arn: str = None,
        **kwargs
    ) -> None:
        """
        Create Cognito User Pool and Identity Pool.

        Args:
            scope: CDK scope
            id: Construct ID
            agentcore_runtime_arn: ARN of AgentCore Runtime for IAM permissions
        """
        super().__init__(scope, id, **kwargs)

        # User Pool
        self._user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="NovaHealthcareUserPool",
            self_sign_up_enabled=False,  # Admin creates demo users
            sign_in_aliases=cognito.SignInAliases(
                username=True,
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # User Pool Client
        self._user_pool_client = self._user_pool.add_client(
            "UserPoolClient",
            user_pool_client_name="NovaHealthcareClient",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            generate_secret=False,
        )

        # Identity Pool
        self._identity_pool = cognito.CfnIdentityPool(
            self,
            "IdentityPool",
            identity_pool_name="NovaHealthcareIdentityPool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self._user_pool_client.user_pool_client_id,
                    provider_name=self._user_pool.user_pool_provider_name,
                )
            ],
        )

        # Authenticated Role for Identity Pool
        self._authenticated_role = iam.Role(
            self,
            "AuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self._identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            description="Role for authenticated users to invoke AgentCore",
        )

        # Grant permission to invoke AgentCore (will be updated when ARN is available)
        if agentcore_runtime_arn:
            self._authenticated_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "bedrock-agentcore:InvokeAgentRuntime",
                        "bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream",
                    ],
                    resources=[agentcore_runtime_arn],
                )
            )

        # Attach role to Identity Pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=self._identity_pool.ref,
            roles={
                "authenticated": self._authenticated_role.role_arn,
            },
        )

        # CDK Nag suppressions — demo project with synthetic test data
        NagSuppressions.add_resource_suppressions(
            self._user_pool,
            [
                {"id": "AwsSolutions-COG1", "reason": "Demo project — symbol requirement omitted for simpler test credentials"},
                {"id": "AwsSolutions-COG2", "reason": "Demo project — MFA unnecessary for synthetic test data"},
                {"id": "AwsSolutions-COG3", "reason": "Demo project — advanced security adds cost with no benefit"},
            ],
        )

    @property
    def user_pool(self) -> cognito.UserPool:
        """User Pool reference."""
        return self._user_pool

    @property
    def user_pool_client(self) -> cognito.UserPoolClient:
        """User Pool Client reference."""
        return self._user_pool_client

    @property
    def identity_pool(self) -> cognito.CfnIdentityPool:
        """Identity Pool reference."""
        return self._identity_pool

    @property
    def authenticated_role(self) -> iam.Role:
        """Authenticated role reference for adding permissions."""
        return self._authenticated_role

    def grant_dynamodb_read(self, table_arns: list) -> None:
        """
        Grant the authenticated role read-only access to DynamoDB tables.

        Args:
            table_arns: List of DynamoDB table ARNs to grant read access to
        """
        self._authenticated_role.add_to_policy(
            iam.PolicyStatement(
                sid="DynamoDBReadAccess",
                actions=[
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:GetItem",
                ],
                resources=table_arns,
            )
        )

    def grant_invoke_agentcore(self, agentcore_runtime_arn: str) -> None:
        """
        Grant the authenticated role permission to invoke AgentCore.

        Args:
            agentcore_runtime_arn: ARN of the AgentCore Runtime
        """
        self._authenticated_role.add_to_policy(
            iam.PolicyStatement(
                sid="InvokeAgentCoreRuntime",
                actions=[
                    # HTTP API invocation
                    "bedrock-agentcore:InvokeAgentRuntime",
                    # WebSocket bidirectional streaming (required for voice)
                    "bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream",
                ],
                # Include both the runtime ARN and the runtime-endpoint subresource
                # WebSocket connections require access to /runtime-endpoint/DEFAULT
                resources=[
                    agentcore_runtime_arn,
                    f"{agentcore_runtime_arn}/runtime-endpoint/*",
                ],
            )
        )
