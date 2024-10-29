#!/usr/bin/env python3
import os

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks
from nice_dcv_with_gateway.nice_dcv_with_gateway_stack import NiceDcvWithGatewayStack


app = cdk.App()
account_id = app.node.get_context("account")
region = app.node.get_context("region")

# cdk.Aspects.of(app).add(AwsSolutionsChecks())

NiceDcvWithGatewayStack(
    app,
    "NiceDcvWithGatewayStack",
    env=cdk.Environment(account=account_id, region=region),
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.
    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.
    # env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */
    # env=cdk.Environment(account='123456789012', region='us-east-1'),
    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
)

app.synth()
