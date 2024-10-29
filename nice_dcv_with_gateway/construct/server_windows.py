from string import Template

from aws_cdk import (
    Resource,
    aws_ec2 as ec2,
    aws_autoscaling as autoscaling,
    aws_iam as iam,
    Stack, Duration,
)
from constructs import Construct


from nice_dcv_with_gateway.construct.server import Server


class WindowsServer(Server):
    def __init__(
        self,
        scope,
        id: str,
        vpc: ec2.Vpc,
        gateway_security_group_id: str,
            authenticator_url: str,
        **kwargs,
    ) -> None:
        super().__init__(
            scope,
            id,
            vpc,
            gateway_security_group_id,
            **kwargs,
        )

        ami = ec2.MachineImage.lookup(
            name="DCV-Windows-*",
            owners=["amazon"],
            windows=True
        )

        with open("scripts/server/user_data.windows.ps", "r") as f:
            user_data = Template(f.read()).safe_substitute(AUTHENTICATOR_URL=authenticator_url)

        self.launch_template = ec2.LaunchTemplate(
            self,
            "LaunchTemplate",
            security_group=self.security_group,
            machine_image=ami,
            user_data=ec2.UserData.custom(user_data),
            role=self.server_iam_role,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.C5, ec2.InstanceSize.LARGE),
            associate_public_ip_address=False,
            launch_template_name=f"{self.node.path}/server",
        )

        self.asg = autoscaling.AutoScalingGroup(
            self,
            "ASG",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            min_capacity=1,
            max_capacity=1,
            launch_template=self.launch_template,
            health_check=autoscaling.HealthCheck.ec2(grace=Duration.minutes(1)),
        )