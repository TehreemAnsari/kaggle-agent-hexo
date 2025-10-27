import os
import json
import time
import boto3

# Environment variables
DDB_TABLE = os.environ["DDB_TABLE"]
S3_BUCKET = os.environ["S3_BUCKET"]
SES_FROM = os.environ["SES_FROM"]
SES_REGION = os.environ.get("SES_REGION", "us-west-2")

# AWS clients
ddb = boto3.resource("dynamodb").Table(DDB_TABLE)
s3 = boto3.client("s3")
ses = boto3.client("ses", region_name=SES_REGION)

def handler(event, context):
    rid = event["run_id"]
    email = event["email"]
    key = event["s3_key"]

    # Update DynamoDB status
    ddb.update_item(
        Key={"run_id": rid},
        UpdateExpression="SET #s = :s, ended_at = :t, s3_key = :k",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "SUCCEEDED",
            ":t": int(time.time()),
            ":k": key
        }
    )

    # Generate a clean, valid presigned S3 URL
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=3600  # 1 hour expiry
    ).strip()

    # Email body (plain text)
    body = (
        f"Hi,\n"
        f"Your Kaggle submission is ready.\n\n"
        f"Download link (valid for 1 hour):\n{url}\n\n"
        f"Run ID: {rid}\n\n"
        f"Thanks,\nKaggle Agent"
    )

    # Send email via SES
    response = ses.send_email(
        Source=SES_FROM,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": f"Kaggle Agent Run Complete: {rid}"},
            "Body": {"Text": {"Data": body}}
        }
    )

    # Log for debugging
    print(f"Email sent! MessageId: {response['MessageId']} to {email}")

    return {"ok": True, "message": "Email sent successfully"}
