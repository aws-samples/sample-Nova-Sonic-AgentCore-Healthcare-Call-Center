"""Clients Package.

AWS service clients for the Healthcare Call Center.
"""

from clients.dynamodb_client import DynamoDBClient
from clients.sns_client import SNSClient

__all__ = ["DynamoDBClient", "SNSClient"]
