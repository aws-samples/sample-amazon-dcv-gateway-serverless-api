import json
import os
import boto3
import time
import base64
from urllib import parse

from botocore.exceptions import ClientError

ec2 = boto3.client("ec2")
dynamodb = boto3.client("dynamodb")
kms = boto3.client("kms")

TABLE_NAME = os.environ.get("DCV_TABLE_NAME")
KMS_KEY = os.environ.get("DCV_KMS_KEY")

def handler(event, context):
    params = dict(parse.parse_qsl(event["body"], strict_parsing=True))

    authToken = params.get("authenticationToken")

    if authToken == None:
        return {
            "statusCode": 200,
            "body": '<auth result="no"><message>Invalid format</message></auth>',
        }

    try:
        token_bytes = base64.urlsafe_b64decode(authToken)
        token_string = kms.decrypt(KeyId=KMS_KEY, CiphertextBlob=token_bytes)["Plaintext"].decode()
        token_payload = json.loads(token_string)
    except ClientError as e:
        return {
            "statusCode": 200,
            "body": '<auth result="no"><message>Invalid token format</message></auth>',
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
                "body": json.dumps({"error": "Unknown sessionId"}),
            }

        expire_at = int(item["Item"]["expire_at"]["N"])
        if expire_at < int(time.time()):
            return {"statusCode": 400, "body": json.dumps({"error": "Expired session"})}

        if secret != item["Item"]["secret"]["S"]:
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid secret"})}

        username = item["Item"]["username"]["S"]
    except ClientError as e:
        return {"statusCode": 404, "body": json.dumps({"error": "Unknown sessionId"})}

    return {
        "statusCode": 200,
        "body": f'<auth result="yes"><username>{username}</username></auth>',
    }

# {"authToken": "AQICAHgWcKRWU0QpY9kF16VHC6Nzat7QlPiM_J63oaGox_djCwF4Zrj4Oqx8wyLV564_Lxh9AAAA_TCB-gYJKoZIhvcNAQcGoIHsMIHpAgEAMIHjBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDPaIIIPgfvyizxfqWwIBEICBtSn55Q_axO_qE_52oH36UGP4Tz8tQtEviaSjU-4tbSV8NyPGaXgyU66gN8oYBPjqNGRHfNd9je-KzU3P_lg6J-pi6rJAZDrdxNtTjczhBpNOZzHu7pd0ZKnt8WfRm1SeSSTsQoZsca4mFEMEgc4Y1SmSDgfL0JMxWEFNEVraBMr3G2vEo4pjfR0bRRhr7CbfIVRqirj4U_mZ09E8NAdSHor9HdNtM8I8Y15nv-TiVwPN14x9AJI=", "sessionId": "778df03a-309d-4c95-b353-20d9db0f94d5"}