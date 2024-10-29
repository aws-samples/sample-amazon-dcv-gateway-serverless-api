import json
import boto3
import time
from urllib import parse

TABLE_NAME = "AuthenticationTokensTable"

def handler(event, context):
    try:
        params = dict(parse.parse_qsl(event['body'], strict_parsing=True))

        authToken = params.get('authenticationToken')
        sessionId = params.get('sessionId')

        if authToken == None or sessionId == None:
            return {
                'statusCode': 200,
                'body': '<auth result="no"><message>Invalid format</message></auth>'
            }

        username = authToken
        return {
            'statusCode': 200,
            'body': '<auth result="yes"><username>' + username + '</username></auth>'
        }

        dynamodb = boto3.client("dynamodb")
        scan = dynamodb.scan(
            TableName=TABLE_NAME,
            FilterExpression="AuthToken = :AuthToken AND SessionId = :SessionId",
            ExpressionAttributeValues={
                ":AuthToken": {"S": authToken},
                ":SessionId": {"S": sessionId}
                }
        )

        count = scan["Count"]
        if count:
            expirationTime = int(scan["Items"][0]["ExpirationTime"]["N"])
            if expirationTime < int(time.time()):
                return {
                    'statusCode': 200,
                    'body': '<auth result="no"><message>Token expired</message></auth>'
                }

            username = scan["Items"][0]["UserName"]["S"]
            return {
                'statusCode': 200,
                'body': '<auth result="yes"><username>' + username + '</username></auth>'
            }
        else:
            return {
                'statusCode': 200,
                'body': '<auth result="no"><message>Authentication token not found</message></auth>'
            }
    except:
        return {
            'statusCode': 200,
            'body': '<auth result="no"><message>Generic error</message></auth>'
        }