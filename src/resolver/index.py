# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import time
import boto3
from botocore.exceptions import ClientError

ec2 = boto3.client("ec2")
dynamodb = boto3.client("dynamodb")
kms = boto3.client("kms")

TABLE_NAME = os.environ.get("DCV_TABLE_NAME")
KMS_KEY = os.environ.get("DCV_KMS_KEY")

TCP_PORT = 8443
UDP_PORT = 8443


def get_instance_ip(instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    private_ip_addr = response["Reservations"][0]["Instances"][0]["PrivateIpAddress"]
    return private_ip_addr


# https://docs.aws.amazon.com/dcv/latest/gw-admin/session-resolver.html#implementing-session-resolver
def handler(event, context):
    # Gateway POST - sessionId=session_id&transport=transport&clientIpAddress=clientIpAddress
    session_id = event["queryStringParameters"]["sessionId"]
    transport = event["queryStringParameters"]["transport"]

    if session_id is None:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing sessionId parameter"}),
        }

    if transport not in ["HTTP", "QUIC"]:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid transport parameter"}),
        }

    try:
        item = dynamodb.get_item(
            TableName=TABLE_NAME, Key={"session_id": {"S": session_id}}
        )
        if not "Item" in item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Unknown sessionId"}),
            }

        expire_at = int(item["Item"]["expire_at"]["N"])
        if expire_at < int(time.time()):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Expired sessionId"}),
            }

        instance_id = item["Item"]["instance_id"]["S"]
        instance_ip = get_instance_ip(instance_id)
    except ClientError as e:
        return {"statusCode": 404, "body": json.dumps({"error": "Unknown sessionId"})}

    port = int(TCP_PORT if transport == "HTTP" else UDP_PORT)
    session_details = {
        "SessionId": "console",
        "DcvServerEndpoint": instance_ip,
        "Port": port,
        "WebUrlPath": "/",
        "TransportProtocol": transport,
    }
    return {"statusCode": 200, "body": json.dumps(session_details)}
