import os, json, re, time, boto3
DDB_TABLE=os.environ["DDB_TABLE"]
ddb=boto3.resource("dynamodb").Table(DDB_TABLE)

def handler(event, context):
    rid, url, email = event["run_id"], event["url"], event["email"]
    m = re.search(r"kaggle\\.com/competitions/([^/?#]+)", url)
    if not m: raise ValueError("Invalid Kaggle URL")
    slug=m.group(1)
    plan={"problem_type":"tabular","model":"random_forest","slug":slug}
    ddb.update_item(Key={"run_id":rid},
        UpdateExpression="SET #s=:s, started_at=:t, plan=:p",
        ExpressionAttributeNames={"#s":"status"},
        ExpressionAttributeValues={":s":"PLANNING",":t":int(time.time()),":p":plan})
    return {"run_id":rid,"url":url,"email":email,"plan":plan}
