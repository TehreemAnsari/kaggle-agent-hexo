import os, subprocess, glob, pandas as pd, re, zipfile
def unzip_all(z,d): zipfile.ZipFile(z,'r').extractall(d)
def plan(url,work_dir):
    import re
    m = re.search(r"kaggle\.com/competitions/([^/?#]+)", url)
    if not m:
        raise ValueError(f"Could not extract competition slug from URL: {url}")
    slug = m.group(1)

    data_dir=os.path.join(work_dir,'data'); os.makedirs(data_dir,exist_ok=True)
    subprocess.run(['kaggle','competitions','download','-c',slug,'-p',data_dir],check=True)
    for z in glob.glob(os.path.join(data_dir,'*.zip')): unzip_all(z,data_dir)
    train, test = sorted(glob.glob(os.path.join(data_dir,'*train*.csv'))), sorted(glob.glob(os.path.join(data_dir,'*test*.csv')))
    train_csv, test_csv = train[0], test[0]
    t=pd.read_csv(train_csv,nrows=5); testd=pd.read_csv(test_csv,nrows=5)
    target=[c for c in t.columns if c not in testd.columns][-1]
    id_col=testd.columns[0]
    return {"problem_type":"tabular","model":"random_forest","train_csv":train_csv,"test_csv":test_csv,"target":target,"id_col":id_col}

if __name__ == "__main__":
    import sys, pprint
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.kaggle.com/competitions/titanic"
    plan_dict = plan(url, ".")
    pprint.pprint(plan_dict)
