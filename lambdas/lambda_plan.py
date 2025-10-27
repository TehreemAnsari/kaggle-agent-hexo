import os, json, re, time, boto3

DDB_TABLE = os.environ["DDB_TABLE"]
ddb = boto3.resource("dynamodb").Table(DDB_TABLE)

def handler(event, context):
    rid, url, email = event["run_id"], event["url"], event["email"]

    # 🧹 Clean up URL in case Step Functions added quotes
    url = str(url).strip().strip('"').strip("'")

    # 🔍 Flexible regex for http/https and www.
    m = re.search(r"https?://(?:www\.)?kaggle\.com/competitions/([^/?#]+)", url)
    if not m:
        print(f"Invalid Kaggle URL received: {url}")
        raise ValueError("Invalid Kaggle URL")

    slug = m.group(1)
    plan = {
        "problem_type": "tabular",
        "model": "random_forest",
        "slug": slug
    }

    # ✅ Use attribute name aliases (#p for plan)
    ddb.update_item(
        Key={"run_id": rid},
        UpdateExpression="SET #s = :s, started_at = :t, #p = :p",
        ExpressionAttributeNames={"#s": "status", "#p": "plan"},
        ExpressionAttributeValues={
            ":s": "PLANNING",
            ":t": int(time.time()),
            ":p": plan
        },
    )

    print(f"✅ Planning completed for slug={slug}")
    return {"run_id": rid, "url": url, "email": email, "plan": plan}