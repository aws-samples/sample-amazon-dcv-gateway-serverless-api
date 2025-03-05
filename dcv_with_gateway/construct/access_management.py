# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from typing import List

from aws_cdk import (
    Resource,
    Stack,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_kms as kms,
    BundlingOptions,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    aws_logs as logs,
)
from constructs import Construct
from cdk_nag import NagSuppressions


class AccessManagement(Resource):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        allowed_execute_api_vpc_endpoint_ids: List[str],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        auth_key = kms.Key(
            self,
            "AuthKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        database = dynamodb.Table(
            self,
            "DcvAccessManagement",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        api_logs = logs.LogGroup(
            self, "DcvAccessManagementApiLogs", removal_policy=RemovalPolicy.DESTROY
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
            deploy_options=apigateway.StageOptions(
                stage_name="v1",
                access_log_destination=apigateway.LogGroupLogDestination(api_logs),
                data_trace_enabled=True,
                logging_level=apigateway.MethodLoggingLevel.INFO,
            ),
        )
        authenticator = lambda_.Function(
            self,
            "Authenticator",
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "src/authenticator",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                ),
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "DCV_KMS_KEY": auth_key.key_id,
                "DCV_TABLE_NAME": database.table_name,
            },
            runtime=lambda_.Runtime.PYTHON_3_13,
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
            code=lambda_.Code.from_asset(
                "src/resolver",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install --no-cache -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                ),
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "DCV_KMS_KEY": auth_key.key_id,
                "DCV_TABLE_NAME": database.table_name,
            },
            runtime=lambda_.Runtime.PYTHON_3_13,
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
            code=lambda_.Code.from_asset(
                "src/create_session",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install --no-cache -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                ),
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "DCV_KMS_KEY": auth_key.key_id,
                "DCV_TABLE_NAME": database.table_name,
                "SESSION_LIFETIME": str(
                    int(self.node.try_get_context("gateway:session-lifetime") or "3600")
                ),
            },
            runtime=lambda_.Runtime.PYTHON_3_13,
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

        # cdk supressions
        NagSuppressions.add_resource_suppressions(
            self.api,
            [
                {
                    "id": "AwsSolutions-APIG2",
                    "reason": "Request validation not required for this internal API",
                },
                {
                    "id": "AwsSolutions-APIG1",
                    "reason": "Access logging not required for sample environment",
                },
                {
                    "id": "AwsSolutions-APIG3",
                    "reason": "WAF not required for sample environment",
                },
                {
                    "id": "AwsSolutions-APIG4",
                    "reason": "Using IAM authorization instead of Cognito",
                },
                {
                    "id": "AwsSolutions-COG4",
                    "reason": "Using IAM authorization instead of Cognito user pools",
                },
            ],
            apply_to_children=True,
        )

        # For Lambda roles (Authenticator, Resolver, CreateSessionHandler)
        NagSuppressions.add_resource_suppressions_by_path(
            Stack.of(self),
            [
                f"/{Stack.of(self).stack_name}/AccessManagement/Authenticator/ServiceRole/Resource",
                f"/{Stack.of(self).stack_name}/AccessManagement/Resolver/ServiceRole/Resource",
                f"/{Stack.of(self).stack_name}/AccessManagement/CreateSessionHandler/ServiceRole/Resource",
            ],
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Using AWS managed policies is acceptable for Lambda execution roles",
                }
            ],
        )

        # For IAM policies with wildcard permissions
        NagSuppressions.add_resource_suppressions_by_path(
            Stack.of(self),
            [
                f"/{Stack.of(self).stack_name}/AccessManagement/Authenticator/ServiceRole/DefaultPolicy/Resource",
                f"/{Stack.of(self).stack_name}/AccessManagement/Resolver/ServiceRole/DefaultPolicy/Resource",
                f"/{Stack.of(self).stack_name}/AccessManagement/CreateSessionHandler/ServiceRole/DefaultPolicy/Resource",
            ],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda functions require specific permissions with wildcards for their operations",
                }
            ],
        )

    @property
    def url(self) -> str:
        return self.api.url
