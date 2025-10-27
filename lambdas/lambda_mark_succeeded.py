import os, json, time, boto3

DDB_TABLE=os.environ["DDB_TABLE"]
S3_BUCKET=os.environ["S3_BUCKET"]
SES_FROM=os.environ["SES_FROM"]
SES_REGION=os.environ.get("SES_REGION")

ddb=boto3.resource("dynamodb").Table(DDB_TABLE)
s3=boto3.client("s3")
ses=boto3.client("ses",region_name=SES_REGION) if SES_REGION else boto3.client("ses")

def handler(event, context):
    rid, email, key = event["run_id"], event["email"], event["s3_key"]
    ddb.update_item(Key={"run_id":rid},
        UpdateExpression="SET #s=:s, ended_at=:t, s3_key=:k",
        ExpressionAttributeNames={"#s":"status"},
        ExpressionAttributeValues={":s":"SUCCEEDED",":t":int(time.time()),":k":key})
    url=s3.generate_presigned_url("get_object",
        Params={"Bucket":S3_BUCKET,"Key":key},ExpiresIn=3600)
    body=(f"Hi,\\nYour Kaggle submission is ready.\\n\\nDownload: {url}\\n\\nRun ID: {rid}\\nThanks.")
    ses.send_email(Source=SES_FROM,
        Destination={"ToAddresses":[email]},
        Message={"Subject":{"Data":f"Kaggle Agent run {rid} done"},
                 "Body":{"Text":{"Data":body}}})
    return {"ok":True}
