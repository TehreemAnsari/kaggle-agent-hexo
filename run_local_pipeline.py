import subprocess, sys, json, pathlib
from agent_like.planner import plan
from agent_like.codegen import generate_training_script

def main():
    url = "https://www.kaggle.com/competitions/titanic"
    run_dir = pathlib.Path("./local_run")
    run_dir.mkdir(exist_ok=True)
    print("🔍 Planning...")
    p = plan(url, str(run_dir))
    print(json.dumps(p, indent=2))

    # Generate code
    print("\n🧠 Generating code...")
    code = generate_training_script(p)
    code_path = run_dir / "train_code.py"
    code_path.write_text(code)
    print(f"✅ Code written to {code_path}")

    # 🔧 Fix: run from the parent dir, not inside local_run again
    print("\n⚙️ Training model and generating submission.csv...")
    result = subprocess.run(
        [sys.executable, str(code_path.resolve())],
        cwd=str(run_dir),
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)

    sub_file = run_dir / "submission.csv"
    if sub_file.exists():
        print(f"✅ submission.csv created at: {sub_file}")
    else:
        print("❌ submission.csv not found!")

if __name__ == "__main__":
    main()
