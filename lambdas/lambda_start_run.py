import os, json, time, uuid, boto3

SFN_ARN   = os.environ["SFN_ARN"]
DDB_TABLE = os.environ["DDB_TABLE"]

sfn = boto3.client("stepfunctions")
ddb = boto3.resource("dynamodb").Table(DDB_TABLE)

def handler(event, context):
    qs = event.get("queryStringParameters") or {}
    url   = qs.get("url")
    email = qs.get("email")
    if not url or not email:
        return {"statusCode":400,"body":json.dumps({"error":"url and email required"})}

    run_id = str(uuid.uuid4())
    now = int(time.time())
    ddb.put_item(Item={
        "run_id":run_id, "url":url, "email":email,
        "status":"QUEUED", "created_at":now
    })

    sfn.start_execution(stateMachineArn=SFN_ARN, input=json.dumps({
        "run_id":run_id, "url":url, "email":email
    }))

    return {
        "statusCode":202,
        "headers":{"Content-Type":"application/json"},
        "body":json.dumps({
            "run_id":run_id,
            "status_url":f"/runs/{run_id}",
            "message":"Accepted"
        })
    }
