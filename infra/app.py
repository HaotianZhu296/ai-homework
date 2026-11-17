#!/usr/bin/env python3
import os
from pathlib import Path

import aws_cdk as cdk

from smarthire.bundle import build_lambda_package
from smarthire.stack import SmartHireStack

HERE = Path(__file__).resolve().parent

app = cdk.App()
SmartHireStack(
    app,
    "SmartHireStack",
    lambda_code_path=build_lambda_package(HERE.parent / "lambda", HERE / ".build" / "lambda"),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-2"),
    ),
    description="hw0-9 SmartHire AI: job requirements (DynamoDB) and resume screening API for Zapier",
)
app.synth()
