"""SmartHireStack: the AWS resources the Zapier workflow calls.

- DynamoDB `JobRequirements` (pk job_id): roles, weighted requirements, advance threshold.
- DynamoDB `Candidates` (pk job_id, sk candidate_email): every evaluation, used for ranking.
- One Python 3.12 Lambda behind an API Gateway REST API. Every method requires an
  API key, which Zapier sends in the `x-api-key` header.
"""

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct


class SmartHireStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, lambda_code_path: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        jobs = dynamodb.Table(
            self,
            "JobRequirements",
            partition_key=dynamodb.Attribute(name="job_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        candidates = dynamodb.Table(
            self,
            "Candidates",
            partition_key=dynamodb.Attribute(name="job_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="candidate_email", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        fn = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={"JOBS_TABLE": jobs.table_name, "CANDIDATES_TABLE": candidates.table_name},
            log_group=logs.LogGroup(
                self,
                "ApiFunctionLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        jobs.grant_read_data(fn)
        candidates.grant_read_write_data(fn)

        api = apigw.RestApi(
            self,
            "SmartHireApi",
            rest_api_name="smarthire-api",
            description="SmartHire AI: job requirements, resume parsing, evaluations and rankings",
            # Multipart uploads reach the Lambda base64-encoded, byte for byte.
            binary_media_types=["multipart/form-data"],
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=10,
                throttling_burst_limit=20,
            ),
            default_method_options=apigw.MethodOptions(api_key_required=True),
        )
        integration = apigw.LambdaIntegration(fn)

        jobs_res = api.root.add_resource("jobs")
        jobs_res.add_method("GET", integration)
        jobs_res.add_resource("{job}").add_method("GET", integration)
        api.root.add_resource("resumes").add_resource("parse").add_method("POST", integration)
        api.root.add_resource("evaluations").add_method("POST", integration)
        api.root.add_resource("rankings").add_resource("{job}").add_method("GET", integration)

        key = api.add_api_key("ZapierKey", api_key_name="smarthire-zapier")
        plan = api.add_usage_plan(
            "ZapierPlan",
            name="smarthire-zapier",
            throttle=apigw.ThrottleSettings(rate_limit=5, burst_limit=10),
            quota=apigw.QuotaSettings(limit=1000, period=apigw.Period.DAY),
        )
        plan.add_api_key(key)
        plan.add_api_stage(stage=api.deployment_stage)

        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "ApiKeyId", value=key.key_id, description="aws apigateway get-api-key --api-key <id> --include-value")
        CfnOutput(self, "JobsTableName", value=jobs.table_name)
        CfnOutput(self, "CandidatesTableName", value=candidates.table_name)
        CfnOutput(self, "FunctionName", value=fn.function_name)
