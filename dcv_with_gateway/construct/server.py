from aws_cdk import (
    Resource,
    aws_ec2 as ec2,
    aws_iam as iam,
    Stack,
)
from constructs import Construct
from cdk_nag import NagSuppressions

class Server(Resource):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        gateway_security_group_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._vpc = vpc

        licence_access_policy = iam.Policy(
            self,
            "LicenceAccessPolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["s3:GetObject"],
                        resources=[
                            f"arn:aws:s3:::dcv-license.{Stack.of(self).region}/*"
                        ],
                        effect=iam.Effect.ALLOW,
                    )
                ]
            ),
        )

        self.server_iam_role = iam.Role(
            self,
            "ServerRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )
        licence_access_policy.attach_to_role(self.server_iam_role)

        self.security_group = ec2.SecurityGroup(
            self,
            "ServerSecurityGroup",
            vpc=vpc,
            description="DCV Server Security Group",
            security_group_name=f"{self.node.path}/server",
        )
        self.security_group.add_ingress_rule(
            ec2.Peer.security_group_id(gateway_security_group_id),
            ec2.Port.tcp(8443),
            "Allow TCP traffic from Gateway",
        )
        self.security_group.add_ingress_rule(
            ec2.Peer.security_group_id(gateway_security_group_id),
            ec2.Port.udp(8443),
            "Allow UDP traffic from Gateway",
        )

        # CDK Nag suppressions
        NagSuppressions.add_resource_suppressions(
            licence_access_policy,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK does not support this use case",
                    "applies_to": f"Resource::arn:aws:s3:::dcv-license.{Stack.of(self).region}/*"
                },
            ]
        )
        NagSuppressions.add_resource_suppressions(
            self.server_iam_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "SSM Managed Instance Core is required for EC2 instance management",
                    "applies_to": "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonSSMManagedInstanceCore"
                },
            ]
        )
