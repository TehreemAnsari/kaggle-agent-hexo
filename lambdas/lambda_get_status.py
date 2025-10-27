import os, json, boto3
DDB_TABLE=os.environ["DDB_TABLE"]
ddb=boto3.resource("dynamodb").Table(DDB_TABLE)

def handler(event,context):
    rid=event.get("pathParameters",{}).get("run_id")
    if not rid: return {"statusCode":400,"body":"missing run_id"}
    res=ddb.get_item(Key={"run_id":rid})
    if "Item" not in res: return {"statusCode":404,"body":"not found"}
    return {"statusCode":200,"body":json.dumps(res["Item"])}
