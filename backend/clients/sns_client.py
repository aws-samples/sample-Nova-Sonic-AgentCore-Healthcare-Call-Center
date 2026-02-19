"""SNS Client for Escalation Notifications.

Publishes escalation notifications to healthcare staff.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SNSClient:
    """Client for escalation notifications via SNS."""

    def __init__(self, topic_arn: Optional[str] = None):
        """Initialize SNS client.

        Args:
            topic_arn: ARN of the escalation SNS topic.
                       Defaults to ESCALATION_TOPIC_ARN environment variable.
        """
        self.topic_arn = topic_arn or os.environ.get("ESCALATION_TOPIC_ARN")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.sns = boto3.client("sns", region_name=self.region)

        if not self.topic_arn:
            logger.warning("ESCALATION_TOPIC_ARN not set - escalations will fail")
        else:
            logger.info("SNS client initialized with topic: %s", self.topic_arn)

    def publish_escalation(
        self, appointment_id: str, patient_id: str, reason: str
    ) -> str:
        """Publish escalation notification.

        Args:
            appointment_id: Appointment ID
            patient_id: Patient ID
            reason: Escalation reason

        Returns:
            SNS message ID

        Raises:
            ValueError: If topic ARN is not configured
            ClientError: If SNS publish fails
        """
        if not self.topic_arn:
            raise ValueError("Escalation topic ARN not configured")

        message = {
            "type": "HEALTHCARE_ESCALATION",
            "timestamp": datetime.now().isoformat(),
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "reason": reason,
        }

        subject = f"Healthcare Call Escalation - {reason[:50]}"

        try:
            response = self.sns.publish(
                TopicArn=self.topic_arn,
                Message=json.dumps(message, indent=2),
                Subject=subject,
                MessageAttributes={
                    "type": {"DataType": "String", "StringValue": "ESCALATION"}
                },
            )

            message_id = response.get("MessageId")
            logger.info("Published escalation with message ID: %s", message_id)
            return message_id

        except ClientError as e:
            logger.error("Failed to publish escalation: %s", e)
            raise
