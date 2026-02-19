"""SNS Construct for escalation notifications."""

from typing import Optional
from aws_cdk import (
    aws_iam as iam,
    aws_kms as kms,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
)
from constructs import Construct


class SNSConstruct(Construct):
    """CDK construct for escalation notifications via SNS."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        escalation_email: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Create SNS topic for healthcare call escalations.

        Args:
            scope: CDK scope
            id: Construct ID
            escalation_email: Optional email address to receive escalation notifications.
                              Configure via cdk.json context "escalation_email".
        """
        super().__init__(scope, id, **kwargs)

        # Escalation Topic (AwsSolutions-SNS2: encrypted with AWS-managed key)
        self._escalation_topic = sns.Topic(
            self,
            "EscalationTopic",
            topic_name="healthcare-escalations",
            display_name="Healthcare Call Escalations",
            master_key=kms.Alias.from_alias_name(self, "SnsKey", "alias/aws/sns"),
        )

        # AwsSolutions-SNS3: enforce HTTPS-only publishing
        self._escalation_topic.add_to_resource_policy(
            iam.PolicyStatement(
                sid="EnforceHTTPS",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sns:Publish"],
                resources=[self._escalation_topic.topic_arn],
                conditions={
                    "Bool": {"aws:SecureTransport": "false"},
                },
            )
        )

        # Add email subscription if provided
        if escalation_email:
            self._escalation_topic.add_subscription(
                sns_subs.EmailSubscription(escalation_email)
            )

    @property
    def escalation_topic(self) -> sns.Topic:
        """Escalation topic reference."""
        return self._escalation_topic

    @property
    def topic_arn(self) -> str:
        """Escalation topic ARN."""
        return self._escalation_topic.topic_arn
