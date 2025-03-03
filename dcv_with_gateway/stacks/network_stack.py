from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
)
from constructs import Construct
from cdk_nag import NagSuppressions

class NetworkStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Resource",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            nat_gateways=2,
            max_azs=2,
            create_internet_gateway=True,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            gateway_endpoints={
                "S3": ec2.GatewayVpcEndpointOptions(
                    service=ec2.GatewayVpcEndpointAwsService.S3
                )
            },
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public-subnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private-subnet",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        self.interface_endpoints = {}
        for service in [
            ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
            ec2.InterfaceVpcEndpointAwsService.SSM,
            ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            ec2.InterfaceVpcEndpointAwsService.KMS,
            ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            ec2.InterfaceVpcEndpointAwsService.APIGATEWAY,
        ]:
            endpoint = self.vpc.add_interface_endpoint(
                service.short_name, service=service
            )
            self.interface_endpoints[service.short_name] = endpoint

        NagSuppressions.add_resource_suppressions(
            self.vpc,
            suppressions=[
                {
                    "id": "AwsSolutions-VPC7",
                    "reason": "VPC Flow Logs are not implemented, code for demonstrating purposes only"
                }
            ]
        )