import os
from textwrap import dedent
from openai import OpenAI

def generate_training_script(plan):
    """
    Universal, no-crash code generator for Kaggle-style tabular datasets.
    Works for any train/test CSV pair, regardless of missing values or non-numeric columns.
    """
    print(f"🚀 Generating training script for {plan.get('model')} ({plan.get('problem_type')})", flush=True)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY in environment.")
    client = OpenAI(api_key=api_key)

    # --- 1️⃣ Universal preprocessing scaffold ---
    scaffold = f"""
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
import numpy as np

# Load data
train_full = pd.read_csv("{plan['train_csv']}")
test_full = pd.read_csv("{plan['test_csv']}")

target = "{plan.get('target')}"
id_col = "{plan.get('id_col')}"

# Drop completely empty columns
train_full = train_full.dropna(axis=1, how='all')
test_full = test_full.dropna(axis=1, how='all')

# Select only numeric columns
train_df = train_full.select_dtypes(include=['number'])
test_df = test_full.select_dtypes(include=['number'])

# Drop id column if present
for col in [id_col]:
    if col and col in train_df.columns:
        train_df = train_df.drop(columns=[col], errors='ignore')
    if col and col in test_df.columns:
        test_df = test_df.drop(columns=[col], errors='ignore')

# Ensure target column exists in train_full
if target not in train_full.columns:
    raise ValueError(f"Target column '{{target}}' not found in train CSV.")

# Drop rows in train_df where target is NaN
train_full = train_full.dropna(subset=[target])

# Match X and y by same index after dropping NaNs
X = train_df.loc[train_full.index]
y = train_full[target].values

# Fill any remaining NaN in features
X = X.fillna(0)
test_df = test_df.fillna(0)

# Align columns between train and test
common_cols = [c for c in X.columns if c in test_df.columns]
X = X[common_cols]
test_df = test_df[common_cols]

# Simple split
if len(X) > 5:
    X_train, X_valid, y_train, y_valid = train_test_split(X, y, test_size=0.2, random_state=42)
else:
    X_train, X_valid, y_train, y_valid = X, X, y, y

print(f"✅ Aligned {{len(common_cols)}} numeric features for training.")
"""

    # --- 2️⃣ Simplified model section ---
    # We no longer depend on GPT codegen for the model — static, safe.
    model_section = """
# Choose model automatically
if len(np.unique(y_train)) <= 20:
    model = RandomForestClassifier(n_estimators=50, random_state=42)
else:
    model = RandomForestRegressor(n_estimators=50, random_state=42)

# Train and predict
model.fit(X_train, y_train)
preds = model.predict(test_df)

# Build submission DataFrame
if id_col and id_col in test_full.columns:
    ids = test_full[id_col]
else:
    ids = range(len(test_df))

submission = pd.DataFrame({id_col: ids, target: preds})
submission.to_csv("submission.csv", index=False)

print("DONE")
"""

    banner = f'print("USING_MODEL: {plan["model"]} TARGET: {plan.get("target", "")}", flush=True)\n'
    full_code = banner + dedent(scaffold + model_section)

    # Save LLM trace (for debugging)
    trace_path = "/work/gpt_code_trace.txt"
    with open(trace_path, "w") as f:
        f.write("Static universal scaffold version — no GPT model code\n")
    print(f"📝 Saved static trace to {trace_path}", flush=True)

    return full_code

# === Local Test ===
if __name__ == "__main__":
    dummy_plan = {
        "train_csv": "data/train.csv",
        "test_csv": "data/test.csv",
        "target": "Survived",
        "id_col": "PassengerId",
        "problem_type": "classification",
        "model": "RandomForest",
    }
    code = generate_training_script(dummy_plan)
    print("\n======= GENERATED CODE =======\n")
    print(code[:700])
