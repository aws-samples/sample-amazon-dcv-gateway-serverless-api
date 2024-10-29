from typing import List

from attr import attributes
from aws_cdk import (
    Resource,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_dynamodb as dynamodb
)
from constructs import Construct


class Authenticator(Resource):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        allowed_execute_api_vpc_endpoint_ids: List[str],
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        database = dynamodb.Table(
            self,
            "Database",
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        handler = lambda_.Function(
            self,
            "Handler",
            handler="index.handler",
            code=lambda_.Code.from_asset("src/authenticator"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
        )

        self.api = apigateway.RestApi(
            self,
            "Resource",
            deploy=True,
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.PRIVATE]
            ),
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["execute-api:Invoke"],
                        principals=[iam.AnyPrincipal()],
                        resources=["*"],
                        effect=iam.Effect.ALLOW,
                        conditions={
                            "StringEquals": {
                                "aws:sourceVpce": allowed_execute_api_vpc_endpoint_ids
                            }
                        },
                    )
                ]
            ),
            deploy_options=apigateway.StageOptions(stage_name="v1"),
        )
        self.api.root.add_method(
            "POST",
            apigateway.LambdaIntegration(handler),
        )

    @property
    def url(self) -> str:
        return self.api.url
