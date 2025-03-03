from string import Template
from aws_cdk import (
    Resource,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_autoscaling as autoscaling,
    Duration, Tags, CfnOutput,
)
from constructs import Construct
from cdk_nag import NagSuppressions


class Gateway(Resource):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        resolver_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.gateway_iam_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
        )

        self.nlb_security_group = ec2.SecurityGroup(
            self,
            "NLBSecurityGroup",
            vpc=vpc,
            description="DCV Gateway NLB Security Group",
            security_group_name=f"{self.node.path}/nlb",
        )

        self.nlb = elbv2.NetworkLoadBalancer(
            self,
            "NLB",
            vpc=vpc,
            internet_facing=True,
            cross_zone_enabled=True,
            security_groups=[self.nlb_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )
        CfnOutput(self, "NLBDNSName", value=self.nlb.load_balancer_dns_name)

        self.nlb_target_group = elbv2.NetworkTargetGroup(
            self,
            "TargetGroup",
            vpc=vpc,
            port=8443,
            protocol=elbv2.Protocol.TCP_UDP,
            preserve_client_ip=True,
            target_type=elbv2.TargetType.INSTANCE,
            health_check=elbv2.HealthCheck(
                enabled=True,
                port="8989",
                protocol=elbv2.Protocol.TCP,
            ),
        )

        self.nlb.add_listener(
            "Listener",
            port=8443,
            protocol=elbv2.Protocol.TCP_UDP,
            default_target_groups=[self.nlb_target_group],
        )

        self.gateway_security_group = ec2.SecurityGroup(
            self,
            "GatewaySecurityGroup",
            vpc=vpc,
            description="DCV Gateway Security Group",
            security_group_name=f"{self.node.path}/gateway",
        )
        self.gateway_security_group.add_ingress_rule(
            ec2.Peer.security_group_id(self.nlb_security_group.security_group_id),
            ec2.Port.tcp(8989),
            "Allow NLB healthcheck",
        )
        self.gateway_security_group.add_ingress_rule(
            ec2.Peer.security_group_id(self.nlb_security_group.security_group_id),
            ec2.Port.tcp(8443),
            "Allow NLB TCP traffic",
        )
        self.gateway_security_group.add_ingress_rule(
            ec2.Peer.security_group_id(self.nlb_security_group.security_group_id),
            ec2.Port.udp(8443),
            "Allow NLB UDP traffic",
        )

        ami = ec2.MachineImage.latest_amazon_linux2(
            cpu_type=ec2.AmazonLinuxCpuType.ARM_64
        )

        with open("scripts/gateway/user_data.linux.sh", "r") as f:
            user_data = Template(f.read()).safe_substitute(RESOLVER_URL=resolver_url)

        self.launch_template = ec2.LaunchTemplate(
            self,
            "LaunchTemplate",
            security_group=self.gateway_security_group,
            user_data=ec2.UserData.custom(user_data),
            machine_image=ami,
            role=self.gateway_iam_role,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.C7G, ec2.InstanceSize.LARGE
            ),
            associate_public_ip_address=False,
            launch_template_name=f"{self.node.path}/gateway",
        )

        self.asg = autoscaling.AutoScalingGroup(
            self,
            "ASG",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            min_capacity=1,
            max_capacity=2,
            launch_template=self.launch_template,
            health_check=autoscaling.HealthCheck.ec2(grace=Duration.minutes(1)),
        )
        Tags.of(self.asg).add("dcv:type", "gateway")

        self.asg.attach_to_network_target_group(self.nlb_target_group)

        # CDK supressions
        NagSuppressions.add_resource_suppressions(
            self.gateway_iam_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "SSM Managed Instance Core is required for EC2 instance management"
                }
            ]
        )

        NagSuppressions.add_resource_suppressions(
            self.nlb,
            [
                {
                    "id": "AwsSolutions-ELB2",
                    "reason": "Access logs not required for samples environment"
                }
            ]
        )

        NagSuppressions.add_resource_suppressions(
            self.asg,
            [
                {
                    "id": "AwsSolutions-AS3",
                    "reason": "Scaling notifications not required for this sample implementation"
                }
            ]
        )

    def add_ingress_rule(
        self, peer: ec2.IPeer, port: ec2.Port, description: str = None
    ):
        self.nlb_security_group.add_ingress_rule(peer, port, description)
        self.gateway_security_group.add_ingress_rule(peer, port, description)
