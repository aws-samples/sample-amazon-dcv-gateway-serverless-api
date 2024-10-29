from platform import architecture
from typing import List

from aws_cdk import (
    Resource,
    aws_ec2 as ec2,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
)
from constructs import Construct


class DcvServer(Resource):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        allowed_execute_api_vpc_endpoint_ids: List[str],
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
