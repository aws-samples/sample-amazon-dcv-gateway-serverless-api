from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct

from nice_dcv_with_gateway.construct.access_management import AccessManagement
from nice_dcv_with_gateway.construct.gateway import Gateway
from nice_dcv_with_gateway.construct.server_linux import ServerLinux
from nice_dcv_with_gateway.construct.server_windows import ServerWindows
from nice_dcv_with_gateway.stacks.network_stack import NetworkStack


class NiceDcvWithGatewayStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        network_stack = NetworkStack(self, "NetworkStack")

        access_management = AccessManagement(
            self,
            "AccessManagement",
            vpc=network_stack.vpc,
            allowed_execute_api_vpc_endpoint_ids=[
                network_stack.interface_endpoints[
                    ec2.InterfaceVpcEndpointAwsService.APIGATEWAY.short_name
                ].vpc_endpoint_id,
            ],
        )

        gateway = Gateway(
            self,
            "Gateway",
            vpc=network_stack.vpc,
            resolver_url=access_management.url,
        )
        allowed_ip_cidr = self.node.try_get_context("allowed-ip-cidr")
        if allowed_ip_cidr:
            gateway.add_ingress_rule(
                peer=ec2.Peer.ipv4(allowed_ip_cidr),
                port=ec2.Port.tcp(8443),
                description="Allow TCP traffic from IP",
            )
            gateway.add_ingress_rule(
                peer=ec2.Peer.ipv4(allowed_ip_cidr),
                port=ec2.Port.udp(8443),
                description="Allow TCP traffic from IP",
            )

        ServerWindows(
            self,
            "WindowsServer",
            vpc=network_stack.vpc,
            gateway_security_group_id=gateway.gateway_security_group.security_group_id,
            authenticator_url=f"{access_management.url}/authenticate",
        )
        ServerLinux(
            self,
            "LinuxServer",
            vpc=network_stack.vpc,
            gateway_security_group_id=gateway.gateway_security_group.security_group_id,
            authenticator_url=f"{access_management.url}/authenticate",
        )
