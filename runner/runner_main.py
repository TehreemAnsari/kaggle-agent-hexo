import os, sys, json, time, subprocess, pathlib, boto3
from agent_like.planner import plan
from agent_like.codegen import generate_training_script

S3_BUCKET=os.environ["S3_BUCKET"]
DDB_TABLE=os.environ["DDB_TABLE"]
RUN_ID=os.environ["RUN_ID"]
URL=os.environ["URL"]
EMAIL=os.environ.get("EMAIL","")

s3=boto3.client("s3")
ddb=boto3.resource("dynamodb").Table(DDB_TABLE)
RUN_DIR=pathlib.Path("/work"); RUN_DIR.mkdir(parents=True,exist_ok=True)

def upload(key, path): s3.upload_file(str(path), S3_BUCKET, key)
def write(path, txt): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(txt)

def main():
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        os.makedirs("/root/.kaggle", exist_ok=True)
        json.dump({"username":os.environ["KAGGLE_USERNAME"],"key":os.environ["KAGGLE_KEY"]},
                  open("/root/.kaggle/kaggle.json","w")); os.chmod("/root/.kaggle/kaggle.json",0o600)

    p=plan(URL,str(RUN_DIR)); write(RUN_DIR/"plan.json",json.dumps(p,indent=2))
    ddb.update_item(Key={"run_id":RUN_ID},
        UpdateExpression="SET #s=:s",ExpressionAttributeNames={"#s":"status"},
        ExpressionAttributeValues={":s":"TRAINING"})

    code=generate_training_script(p); code_path=RUN_DIR/"train_code.py"; write(code_path,code)
    proc=subprocess.run([sys.executable,str(code_path)],cwd=str(RUN_DIR),capture_output=True,text=True)
    write(RUN_DIR/"logs.txt",proc.stdout+"\n=== STDERR ===\n"+proc.stderr)
    upload(f"runs/{RUN_ID}/logs.txt",RUN_DIR/"logs.txt")
    if proc.returncode!=0:
        ddb.update_item(Key={"run_id":RUN_ID},
          UpdateExpression="SET #s=:s, error=:e",
          ExpressionAttributeNames={"#s":"status"},
          ExpressionAttributeValues={":s":"FAILED",":e":"training failed"})
        sys.exit(1)
    sub=RUN_DIR/"submission.csv"
    upload(f"runs/{RUN_ID}/submission.csv",sub)

if __name__=="__main__": main()
