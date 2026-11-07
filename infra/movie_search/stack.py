"""Single CDK stack: OpenSearch domain + search Lambda + REST API (GET /search)."""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_opensearchservice as opensearch,
)
from constructs import Construct

INDEX_NAME = "movies"


class MovieSearchStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, lambda_code_path: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- OpenSearch: 1 x t3.small.search, 10 GB EBS -----------------------
        domain = opensearch.Domain(
            self,
            "MoviesDomain",
            domain_name="movie-search",
            version=opensearch.EngineVersion.OPENSEARCH_2_19,
            capacity=opensearch.CapacityConfig(
                data_nodes=1,
                data_node_instance_type="t3.small.search",
                multi_az_with_standby_enabled=False,
            ),
            ebs=opensearch.EbsOptions(
                enabled=True,
                volume_size=10,
                volume_type=ec2.EbsDeviceVolumeType.GP3,
            ),
            zone_awareness=opensearch.ZoneAwarenessConfig(enabled=False),
            enforce_https=True,
            node_to_node_encryption=True,
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- Lambda (Python 3.12) ---------------------------------------------
        search_fn = lambda_.Function(
            self,
            "SearchFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(10),
            memory_size=256,
            environment={
                "OPENSEARCH_ENDPOINT": f"https://{domain.domain_endpoint}",
                "INDEX_NAME": INDEX_NAME,
            },
            log_group=logs.LogGroup(
                self,
                "SearchFunctionLogs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        # Least privilege: the function may only run searches on the movies index.
        search_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["es:ESHttpGet", "es:ESHttpPost"],
                resources=[f"{domain.domain_arn}/{INDEX_NAME}/_search"],
            )
        )

        # --- API Gateway REST API: GET /search with CORS ----------------------
        api = apigw.RestApi(
            self,
            "MovieSearchApi",
            rest_api_name="movie-search-api",
            description="Keyword search over the movies index",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "OPTIONS"],
                allow_headers=["Content-Type"],
            ),
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=20,
                throttling_burst_limit=40,
            ),
        )
        search = api.root.add_resource("search")
        search.add_method(
            "GET",
            apigw.LambdaIntegration(search_fn),
            request_parameters={"method.request.querystring.q": False},
        )

        CfnOutput(self, "ApiUrl", value=api.url, description="Base URL for the frontend (VITE_API_URL)")
        CfnOutput(self, "SearchUrl", value=f"{api.url}search", description="GET ?q=<keywords>")
        CfnOutput(self, "OpenSearchEndpoint", value=f"https://{domain.domain_endpoint}")
        CfnOutput(self, "SearchFunctionName", value=search_fn.function_name)
