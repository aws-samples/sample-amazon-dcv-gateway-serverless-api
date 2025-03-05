# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import boto3
import time
import base64
from urllib import parse

from botocore.exceptions import ClientError
from typing import Optional
from pydantic import BaseModel, Field
from xmltodict import unparse

ec2 = boto3.client("ec2")
dynamodb = boto3.client("dynamodb")
kms = boto3.client("kms")

TABLE_NAME = os.environ.get("DCV_TABLE_NAME")
KMS_KEY = os.environ.get("DCV_KMS_KEY")


class Auth(BaseModel):
    class Config:
        populate_by_name = True

    result: Optional[str] = Field(None, alias="_result", title="Result")
    username: Optional[str] = Field(None, title="Username")
    message: Optional[str] = Field(None, title="Error message")


class AuthenticateResponse(BaseModel):
    class Config:
        populate_by_name = True

    auth: Auth

    def to_xml(self):
        return unparse(self.model_dump(by_alias=True), attr_prefix="_")


def get_instance_ip(instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    private_ip_addr = response["Reservations"][0]["Instances"][0]["PrivateIpAddress"]
    return private_ip_addr


def handler(event, context):
    params = dict(parse.parse_qsl(event["body"], strict_parsing=True))

    authToken = params.get("authenticationToken")
    source_ip = event.get("requestContext").get("identity").get("sourceIp")

    if authToken == None:
        return {
            "statusCode": 400,
            "body": AuthenticateResponse(
                auth=Auth(result="no", message="Invalid format")
            ).to_xml(),
        }

    try:
        token_bytes = base64.urlsafe_b64decode(authToken)
        token_string = kms.decrypt(KeyId=KMS_KEY, CiphertextBlob=token_bytes)[
            "Plaintext"
        ].decode()
        token_payload = json.loads(token_string)
    except ClientError as e:
        return {
            "statusCode": 400,
            "body": AuthenticateResponse(
                auth=Auth(result="no", message="Invalid token format")
            ).to_xml(),
        }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": AuthenticateResponse(
                auth=Auth(result="no", message="Invalid token format")
            ).to_xml(),
        }

    session_id = token_payload["session_id"]
    secret = token_payload["secret"]
    try:
        item = dynamodb.get_item(
            TableName=TABLE_NAME, Key={"session_id": {"S": session_id}}
        )
        if not "Item" in item:
            return {
                "statusCode": 404,
                "body": AuthenticateResponse(
                    auth=Auth(result="no", message="Session not found")
                ).to_xml(),
            }

        expire_at = int(item["Item"]["expire_at"]["N"])
        if expire_at < int(time.time()):
            return {
                "statusCode": 400,
                "body": AuthenticateResponse(
                    auth=Auth(result="no", message="Expired session")
                ).to_xml(),
            }

        activated_at = int(item["Item"]["activated_at"]["N"])
        if activated_at > 0:
            return {
                "statusCode": 400,
                "body": AuthenticateResponse(
                    auth=Auth(result="no", message="Session already activated")
                ).to_xml(),
            }

        if source_ip != get_instance_ip(item["Item"]["instance_id"]["S"]):
            return {
                "statusCode": 400,
                "body": AuthenticateResponse(
                    auth=Auth(result="no", message="Unknown origin")
                ).to_xml(),
            }

        if secret != item["Item"]["secret"]["S"]:
            return {
                "statusCode": 400,
                "body": AuthenticateResponse(
                    auth=Auth(result="no", message="Invalid secret")
                ).to_xml(),
            }

        username = item["Item"]["username"]["S"]

        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={"session_id": {"S": session_id}},
            UpdateExpression="SET #attr = :val",
            ConditionExpression="#attr = :zero",
            ExpressionAttributeNames={"#attr": "activated_at"},
            ExpressionAttributeValues={
                ":val": {"N": str(int(time.time()))},
                ":zero": {"N": "0"},
            },
        )
    except ClientError as e:
        return {
            "statusCode": 400,
            "body": AuthenticateResponse(
                auth=Auth(result="no", message="Unknown error")
            ).to_xml(),
        }

    return {
        "statusCode": 200,
        "body": AuthenticateResponse(
            auth=Auth(result="yes", username=username)
        ).to_xml(),
    }
