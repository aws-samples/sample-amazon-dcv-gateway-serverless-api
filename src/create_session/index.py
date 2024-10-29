import os
import boto3
import time
from urllib import parse
from botocore.exceptions import ClientError

ec2 = boto3.client("ec2")

TABLE_NAME = os.environ.get('DCV_TABLE_NAME')
KMS_KEY = os.environ.get('DCV_KMS_KEY')

class InstanceDetails:
    enabled: bool
    user: str
    private_ip_addr: str


def get_instance_details(instance_id):
    """Given an instance ID this returns the private Ip address and DCV tags corresponding to it"""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        private_ip_addr = response["Reservations"][0]["Instances"][0][
            "PrivateIpAddress"
        ]
        platform = response["Reservations"][0]["Instances"][0]["PlatformDetails"]

        tags = response["Reservations"][0]["Instances"][0]["Tags"]
        dcv_enabled = next(
            (tag for tag in tags if tag["Key"] == "dcv:type" and tag["Value"] == "server"), None
        )

        # Tags.of(self.asg).add("dcv:type", "server")
        # Tags.of(self.asg).add("dcv:platform", "windows")
        # Tags.of(self.asg).add("dcv:user", "Administrator")
        # Tags.of(self.asg).add("dcv:session:autogenerate", "true")



        return private_ip_addr
    except ClientError:
        return {"statusCode": 404, "body": f"Invalid session ID '{instance_id}'."}


def handler(event, context):
    instance_id = event.get("detail", {}).get("EC2InstanceId")

    if instance_id:


    try:

        params = dict(parse.parse_qsl(event["body"], strict_parsing=True))

        authToken = params.get("authenticationToken")
        sessionId = params.get("sessionId")

        if authToken == None or sessionId == None:
            return {
                "statusCode": 200,
                "body": '<auth result="no"><message>Invalid format</message></auth>',
            }

        username = authToken
        return {
            "statusCode": 200,
            "body": '<auth result="yes"><username>' + username + "</username></auth>",
        }

        dynamodb = boto3.client("dynamodb")
        scan = dynamodb.scan(
            TableName=TABLE_NAME,
            FilterExpression="AuthToken = :AuthToken AND SessionId = :SessionId",
            ExpressionAttributeValues={
                ":AuthToken": {"S": authToken},
                ":SessionId": {"S": sessionId},
            },
        )

        count = scan["Count"]
        if count:
            expirationTime = int(scan["Items"][0]["ExpirationTime"]["N"])
            if expirationTime < int(time.time()):
                return {
                    "statusCode": 200,
                    "body": '<auth result="no"><message>Token expired</message></auth>',
                }

            username = scan["Items"][0]["UserName"]["S"]
            return {
                "statusCode": 200,
                "body": '<auth result="yes"><username>'
                + username
                + "</username></auth>",
            }
        else:
            return {
                "statusCode": 200,
                "body": '<auth result="no"><message>Authentication token not found</message></auth>',
            }
    except:
        return {
            "statusCode": 200,
            "body": '<auth result="no"><message>Generic error</message></auth>',
        }
