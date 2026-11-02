# Publish this project to GitHub

This archive is a source package. **Extract it before pushing**; GitHub will not unpack a ZIP uploaded as a repository file.

## Recommended repository

- GitHub account: `om-prakash16`
- Repository name: `yotta`
- Visibility: **Public**
- Expected repository URL: `https://github.com/om-prakash16/yotta`

The URL above is the intended URL, not a claim that the repository has already been created or published.

## Windows PowerShell

1. Extract `YottaFlex_Round2_GitHub_Ready_Final.zip`.
2. Open PowerShell in the extracted `yottaflex-school-transport-optimizer` folder.
3. Run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pytest -q
python -m busroute validate --data datasets/starter/data --ground-truth datasets/starter/ground_truth/ground_truth.csv
python scripts/verify_sqlite_seed.py --seed datasets/starter/data/seed.sql
```

4. Create an **empty, public** GitHub repository named `yottaflex-school-transport-optimizer` under `omprakash-16`. Do not initialise it with a README, license or `.gitignore` because those files are already in this package.
5. Push the project:

```powershell
git init
git add .
git commit -m "Build deterministic school bus routing and attendance simulator"
git branch -M main
git remote add origin https://github.com/om-prakash16/yotta.git
git push -u origin main
```

## Before sharing the client link

- Open the repository in a private/incognito browser window and confirm it is publicly readable.
- Confirm the README, source, starter dataset, tests, CI workflow and documentation are visible.
- Do not upload full-scale generated exports; they are reproducible and are intentionally excluded from this repository package.
- Share `https://github.com/om-prakash16/yotta` only after the push succeeds and the public page is verified.
- Submit the same verified public URL in the YottaFlex portal. The portal says the submission is final, so check the URL before submitting.
