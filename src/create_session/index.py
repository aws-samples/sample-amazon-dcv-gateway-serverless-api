import json
import os
import secrets
import base64

import boto3
import time
import uuid
from botocore.exceptions import ClientError

ec2 = boto3.client("ec2")
dynamodb = boto3.client("dynamodb")
kms = boto3.client("kms")

TABLE_NAME = os.environ.get("DCV_TABLE_NAME")
KMS_KEY = os.environ.get("DCV_KMS_KEY")


def get_instance_tags(instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    tags = response["Reservations"][0]["Instances"][0]["Tags"]
    return dict((tag["Key"], tag["Value"]) for tag in tags)


def handler(event, context):
    if not "instanceId" in event["queryStringParameters"]:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Parameter instanceId is required"}),
        }

    instance_id = event["queryStringParameters"]["instanceId"]
    try:
        tags = get_instance_tags(instance_id)
    except ClientError:
        return {"statusCode": 404, "body": json.dumps({"error": "Invalid instanceId"})}

    if tags.get("dcv:type") != "server" or not tags.get("dcv:user"):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Instance has no required tags"}),
        }

    session_id = str(uuid.uuid4())
    secret = str(secrets.token_urlsafe(64))

    auth_token_bytes = kms.encrypt(
        KeyId=KMS_KEY, Plaintext=json.dumps({"session_id": session_id, "secret": secret})
    )["CiphertextBlob"]
    auth_token=base64.urlsafe_b64encode(auth_token_bytes)

    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            "session_id": {"S": session_id},
            "secret": {"S": secret},
            "instance_id": {"S": instance_id},
            "username": {"S": tags.get("dcv:user")},
            "created_at":{"N": str(int(time.time()))},
            "expire_at": {"N": str(int(time.time()) + 3600)},
            "activated_at": {"N": "0"}
        },
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"authToken": auth_token.decode(), "sessionId": session_id}),
    }
