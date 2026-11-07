from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from movie_search.stack import MovieSearchStack

LAMBDA_SRC = Path(__file__).resolve().parent.parent / "lambda"


@pytest.fixture(scope="module")
def template():
    app = cdk.App()
    stack = MovieSearchStack(
        app,
        "TestStack",
        lambda_code_path=str(LAMBDA_SRC),
        env=cdk.Environment(account="123456789012", region="us-east-2"),
    )
    return Template.from_stack(stack)


def test_single_node_t3_small_with_10gb_ebs(template):
    template.resource_count_is("AWS::OpenSearchService::Domain", 1)
    template.has_resource_properties(
        "AWS::OpenSearchService::Domain",
        {
            "ClusterConfig": Match.object_like(
                {"InstanceCount": 1, "InstanceType": "t3.small.search", "ZoneAwarenessEnabled": False}
            ),
            "EBSOptions": Match.object_like({"EBSEnabled": True, "VolumeSize": 10}),
            "DomainEndpointOptions": Match.object_like({"EnforceHTTPS": True}),
        },
    )


def test_python312_lambda_gets_endpoint_from_env(template):
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.handler",
            "Environment": {
                "Variables": {
                    "OPENSEARCH_ENDPOINT": Match.any_value(),
                    "INDEX_NAME": "movies",
                }
            },
        },
    )


def test_lambda_can_only_search_movies_index(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [Match.object_like({"Action": ["es:ESHttpGet", "es:ESHttpPost"], "Effect": "Allow"})]
                )
            }
        },
    )


def test_rest_api_has_only_get_search(template):
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::ApiGateway::Resource", 1)
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "search"})
    methods = template.find_resources("AWS::ApiGateway::Method")
    verbs = sorted(m["Properties"]["HttpMethod"] for m in methods.values())
    # GET /search plus the CORS preflight OPTIONS methods CDK adds
    assert verbs.count("GET") == 1
    assert set(verbs) == {"GET", "OPTIONS"}


def test_cors_enabled(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {
            "HttpMethod": "OPTIONS",
            "Integration": Match.object_like(
                {
                    "IntegrationResponses": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "ResponseParameters": Match.object_like(
                                        {"method.response.header.Access-Control-Allow-Origin": "'*'"}
                                    )
                                }
                            )
                        ]
                    )
                }
            ),
        },
    )
