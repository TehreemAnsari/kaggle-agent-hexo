import os, subprocess, glob, zipfile, re, pandas as pd, json
from textwrap import shorten
from openai import OpenAI

def unzip_all(z, d):
    import zipfile as _zip
    with _zip.ZipFile(z, 'r') as zip_ref:
        zip_ref.extractall(d)

def _print_head(df, n=5):
    try:
        return df.head(n).to_dict(orient="records")
    except Exception:
        return []

def plan(url, work_dir):
    """
    Agentic planner with robust logging:
    - Downloads dataset from Kaggle
    - Reads sample of train/test
    - Calls GPT to infer problem type/target/model
    - Emits clear CloudWatch logs and returns a structured plan
    - Falls back gracefully if LLM fails
    """
    print("🔑 OPENAI_API_KEY present:", bool(os.getenv("OPENAI_API_KEY")) , flush=True)
    client = None
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # simple sanity call (won't bill much, but verifies key)
        # we skip a ping; main call below will surface any auth error
    except Exception as e:
        print("❌ Could not initialize OpenAI client:", str(e), flush=True)

    m = re.search(r"(?:www\.)?kaggle\.com/competitions/([^/?#]+)", url)
    if not m:
        raise ValueError(f"Could not extract competition slug from URL: {url}")
    slug = m.group(1)
    print(f"🏷️ Competition slug: {slug}", flush=True)

    # Download
    data_dir = os.path.join(work_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    print(f"⬇️ Downloading data into {data_dir}", flush=True)
    try:
        res = subprocess.run(
            ["kaggle", "competitions", "download", "-c", slug, "-p", data_dir],
            check=True, capture_output=True, text=True
        )
        # kaggle prints progress to stderr; print both for clarity
        if res.stdout: print(res.stdout, flush=True)
        if res.stderr: print(res.stderr, flush=True)
    except subprocess.CalledProcessError as e:
        err = (e.stdout or "") + "\n" + (e.stderr or "")
        if "403 - Forbidden" in err:
            print(f"⚠️ Kaggle says you must accept rules for {slug}.", flush=True)
        print("💥 Kaggle download failed:", err, flush=True)
        raise

    for z in glob.glob(os.path.join(data_dir, "*.zip")):
        unzip_all(z, data_dir)

    # Find CSVs
    train = sorted(glob.glob(os.path.join(data_dir, "*train*.csv")))
    test  = sorted(glob.glob(os.path.join(data_dir, "*test*.csv")))
    if not train or not test:
        raise ValueError("Could not find train/test CSVs in downloaded data")
    train_csv, test_csv = train[0], test[0]
    print(f"📄 train_csv={train_csv} | test_csv={test_csv}", flush=True)

    # Sample for reasoning
    df_train = pd.read_csv(train_csv, nrows=200)
    df_test  = pd.read_csv(test_csv,  nrows=50)

    # Heuristic: ID & target candidates
    candidate_targets = [c for c in df_train.columns if c not in df_test.columns]
    id_candidates = [c for c in df_test.columns if df_test[c].is_unique] or [df_test.columns[0]]

    schema = {
        "columns": list(df_train.columns),
        "dtypes": df_train.dtypes.astype(str).to_dict(),
        "head": _print_head(df_train, 5),
        "target_candidates": candidate_targets[:5],
        "id_candidates": id_candidates[:3],
        "shape_train": df_train.shape,
        "shape_test": df_test.shape,
    }
    print("🧾 Schema snapshot:", json.dumps(schema, indent=2)[:2000], flush=True)

    # Prompt
    prompt = f"""
You are a Kaggle competition planning agent.

Dataset info:
- Columns and types: {json.dumps(schema['dtypes'], indent=2)}
- Head of training data: {json.dumps(schema['head'], indent=2)}
- Train shape: {schema['shape_train']}
- Test shape: {schema['shape_test']}
- Target candidates (train-only cols): {candidate_targets[:5]}
- ID candidates (unique in test): {id_candidates[:3]}

Decide:
1. problem_type: one of ["classification","regression","nlp","image","time_series","tabular"]
2. target: best guess from candidates (or fallback)
3. model: suitable family (RandomForest, XGBoost, LogisticRegression, LightGBM, CNN, Transformer, LSTM/Prophet)
4. id_col: ID column for submission (choose from candidates)
5. notes: brief rationale

Return ONLY a JSON object with keys: problem_type, target, model, id_col, notes
"""

    parsed = None
    if client:
        try:
            print("🧠 Calling OpenAI to reason about dataset...", flush=True)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                messages=[
                    {"role": "system", "content": "You are an expert ML data scientist."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            print("🧩 GPT raw:", shorten(raw, width=1000, placeholder="…"), flush=True)

            # extract first JSON object
            m2 = re.search(r"\{.*\}", raw, re.S)
            if m2:
                parsed = json.loads(m2.group(0))
                parsed["model_source"] = "llm"
            else:
                print("⚠️ No JSON found in GPT output, will fallback.", flush=True)
        except Exception as e:
            print("💥 OpenAI error:", str(e), flush=True)

    if not parsed:
        # Basic heuristics to make it visibly NOT always random_forest
        # (e.g., MNIST-like: many pixel* columns)
        cols = list(df_train.columns)
        numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df_train[c])]
        pixel_like = sum(1 for c in cols if re.match(r"pixel\\d+$", c))
        if candidate_targets:
            target = candidate_targets[0]
        else:
            # simple: last column if cannot infer
            target = cols[-1]
        id_col = id_candidates[0]

        if pixel_like > 500 or len(numeric_cols) > 500:
            model = "mlp_classifier"  # Different from RF to prove variation
            problem_type = "classification"
            notes = "Heuristic: many pixel-like columns; using MLP."
        else:
            model = "random_forest"
            problem_type = "tabular"
            notes = "Fallback heuristic plan (LLM parse failed)."

        parsed = {
            "problem_type": problem_type,
            "target": target,
            "model": model,
            "id_col": id_col,
            "notes": notes,
            "model_source": "fallback",
        }

    parsed["train_csv"] = train_csv
    parsed["test_csv"] = test_csv
    parsed["slug"] = slug

    print("✅ Final plan:", json.dumps(parsed, indent=2), flush=True)
    return parsed

if __name__ == "__main__":
    import sys, pprint
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.kaggle.com/competitions/house-prices-advanced-regression-techniques"
    plan_dict = plan(url, ".")
    pprint.pprint(plan_dict)