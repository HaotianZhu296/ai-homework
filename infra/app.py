#!/usr/bin/env python3
import os
from pathlib import Path

import aws_cdk as cdk

from movie_search.bundle import build_lambda_package
from movie_search.stack import MovieSearchStack

HERE = Path(__file__).resolve().parent

app = cdk.App()
MovieSearchStack(
    app,
    "MovieSearchStack",
    lambda_code_path=build_lambda_package(HERE.parent / "lambda", HERE / ".build" / "lambda"),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-2"),
    ),
    description="hw0-4 movie keyword search: OpenSearch + Lambda + API Gateway",
)
app.synth()
