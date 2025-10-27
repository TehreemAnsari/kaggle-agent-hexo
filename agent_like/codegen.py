from textwrap import dedent
import os

def generate_training_script(p):
    # Convert any absolute path to relative-from run_dir (e.g. remove "local_run/")
    train_path = os.path.basename(p["train_csv"]) if "local_run" in p["train_csv"] else p["train_csv"]
    test_path = os.path.basename(p["test_csv"]) if "local_run" in p["test_csv"] else p["test_csv"]

    return dedent(f"""\
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Load data (now relative paths, since cwd=local_run)
train = pd.read_csv(os.path.abspath("data/train.csv"))
test = pd.read_csv(os.path.abspath("data/test.csv"))

X = train.drop(columns=["{p['target']}"])
y = train["{p['target']}"]

X = X.fillna(0)
test = test.fillna(0)

X = pd.get_dummies(X)
test = pd.get_dummies(test).reindex(columns=X.columns, fill_value=0)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X, y)
pred = model.predict(test)

sub = pd.DataFrame({{"{p['id_col']}": test["{p['id_col']}"], "{p['target']}": pred}})
sub.to_csv("submission.csv", index=False)
print("✅ done, saved to:", os.path.abspath("submission.csv"))
""")
