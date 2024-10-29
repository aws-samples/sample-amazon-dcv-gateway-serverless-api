from typing import List

from aws_cdk import (
    Resource,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_kms as kms,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class AccessManagement(Resource):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        allowed_execute_api_vpc_endpoint_ids: List[str],
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        auth_key = kms.Key(
            self,
            "AuthKey",
            enable_key_rotation=True,
        )
        auth_key.add_alias("alias/dcv-access-management")
        database = dynamodb.Table(
            self,
            "DcvAccessManagement",
            table_name="dcv_access_management",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        self.api = apigateway.RestApi(
            self,
            "DcvAccessManagementApi",
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

        authenticator = lambda_.Function(
            self,
            "Authenticator",
            handler="index.handler",
            code=lambda_.Code.from_asset("src/authenticator"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "DCV_KMS_KEY": auth_key.key_id,
                "DCV_TABLE_NAME": database.table_name,
            },
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            initial_policy=[
                iam.PolicyStatement(
                    actions=["ec2:DescribeInstances"],
                    resources=["*"],
                )
            ],
        )
        auth_key.grant_decrypt(authenticator)
        database.grant_read_write_data(authenticator)
        self.api.root.add_resource("authenticate").add_method(
            "POST",
            apigateway.LambdaIntegration(authenticator),
        )

        resolver = lambda_.Function(
            self,
            "Resolver",
            handler="index.handler",
            code=lambda_.Code.from_asset("src/resolver"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "DCV_KMS_KEY": auth_key.key_id,
                "DCV_TABLE_NAME": database.table_name,
            },
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            initial_policy=[
                iam.PolicyStatement(
                    actions=["ec2:DescribeInstances"],
                    resources=["*"],
                )
            ],
        )
        auth_key.grant_decrypt(resolver)
        database.grant_read_write_data(resolver)
        self.api.root.add_resource("resolveSession").add_method(
            "POST",
            apigateway.LambdaIntegration(resolver),
        )

        create_session = lambda_.Function(
            self,
            "CreateSessionHandler",
            handler="index.handler",
            code=lambda_.Code.from_asset("src/create_session"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "DCV_KMS_KEY": auth_key.key_id,
                "DCV_TABLE_NAME": database.table_name,
            },
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            initial_policy=[
                iam.PolicyStatement(
                    actions=["ec2:DescribeInstances"],
                    resources=["*"],
                )
            ],
        )
        auth_key.grant_encrypt(create_session)
        database.grant_read_write_data(create_session)
        self.api.root.add_resource("session").add_method(
            "POST",
            apigateway.LambdaIntegration(create_session),
            authorization_type=apigateway.AuthorizationType.IAM,
        )

    @property
    def url(self) -> str:
        return self.api.url
