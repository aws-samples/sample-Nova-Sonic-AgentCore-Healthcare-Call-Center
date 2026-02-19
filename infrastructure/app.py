#!/usr/bin/env python3
"""CDK Application entry point for Nova Sonic Healthcare Call Center."""

import os

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks
from stacks.healthcare_stack import HealthcareStack

app = cdk.App()

HealthcareStack(
    app,
    "NovaSonicHealthcareStack",
    description="Nova Sonic Healthcare Call Center with AgentCore + BidiAgent",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    )
)

cdk.Tags.of(app).add("project", "nova-sonic-hcls-call-center")
cdk.Aspects.of(app).add(AwsSolutionsChecks())

app.synth()
