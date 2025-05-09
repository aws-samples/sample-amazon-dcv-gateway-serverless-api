# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from string import Template

from aws_cdk import (
    aws_ec2 as ec2,
    aws_autoscaling as autoscaling,
    Duration,
    Tags,
)
from cdk_nag import NagSuppressions

from dcv_with_gateway.construct.server import Server


class ServerWindows(Server):
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
            name="DCV-Windows-*", owners=["amazon"], windows=True
        )

        with open("scripts/server/user_data.windows.ps", "r") as f:
            user_data = Template(f.read()).safe_substitute(
                AUTHENTICATOR_URL=authenticator_url
            )

        self.launch_template = ec2.LaunchTemplate(
            self,
            "LaunchTemplate",
            security_group=self.security_group,
            machine_image=ami,
            user_data=ec2.UserData.custom(user_data),
            role=self.server_iam_role,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.C5, ec2.InstanceSize.LARGE
            ),
            associate_public_ip_address=False,
            launch_template_name=f"{self.node.path}/server",
            require_imdsv2=True,
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
        Tags.of(self.asg).add("dcv:type", "server")
        Tags.of(self.asg).add("dcv:user", "Administrator")

        # CDK Nag suppressions
        NagSuppressions.add_resource_suppressions(
            self.asg,
            [
                {
                    "id": "AwsSolutions-AS3",
                    "reason": "Scaling notifications not required for this sample implementation",
                }
            ],
        )
