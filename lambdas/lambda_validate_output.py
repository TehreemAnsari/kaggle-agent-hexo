import os, json, boto3, csv
S3_BUCKET=os.environ["S3_BUCKET"]
s3=boto3.client("s3")

def handler(event,context):
    rid, email = event["run_id"], event["email"]
    key=f"runs/{rid}/submission.csv"
    obj=s3.get_object(Bucket=S3_BUCKET,Key=key)
    lines=obj["Body"].read(2048).decode("utf-8").splitlines()
    reader=csv.reader(lines)
    cols=next(reader)
    if not cols: raise ValueError("Empty submission")
    return {"run_id":rid,"email":email,"s3_key":key}
