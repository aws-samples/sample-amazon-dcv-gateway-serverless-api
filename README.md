# AWS Samples - DCV gateway access management

## Quick start

1. Create `cdk.context.json` file with following content:
```
{
  "allowed-ip-cidr": "yourIP",
  "account": "account-id - required to search for AMIs",
  "region": "region - required to search for AMIs"
}

```
2. Run `cdk deploy` to deploy the stack
3. Open EC2 console and copy instanceId of either windows or linux instance (check how instances are tagged) 
4. Open API gateway console, select `DcvAccessManagementApi`
5. Test `POST session` endpoint with following query string `instanceId={instanceId}`. It does create session valid for 1h. 
6. Copy NLB DNS and craft url like this `https://{DNS}:8443?authToken={token}#{sessionId}`
