# YottaFlex Round 2 submission checklist

## Repository contents

- [x] Python source for the generator, assignment rules, attendance simulation, anomaly injection, validator, metrics and CLI.
- [x] Deterministic starter CSV/JSON/SQL dataset and separate ground-truth labels.
- [x] Schema, data dictionary, assumptions, reviewer walkthrough and AI-use disclosure.
- [x] Automated regression tests and GitHub Actions CI workflow.
- [x] Full-scale manifest, clean-baseline metrics/validation, exported-data validation, SQLite import evidence and two-run SHA-256 report.

## Before publishing

1. Create a new **public** GitHub repository, for example `yottaflex-school-transport-optimizer`.
2. Extract this ZIP and open a terminal in the project root.
3. Run `python -m pip install -r requirements-lock.txt` and `python -m pytest -q`.
4. Confirm the starter data validation and SQLite check pass using the commands in `docs/REVIEWER_WALKTHROUGH.md`.
5. Push the source and starter data. Do not add `datasets/full/` or `datasets/full_run*/` to Git; those large files are reproducible with the documented full-profile command and exceed GitHub's per-file upload limit.
6. Check the GitHub repository visibility is **Public**, open the repository in a signed-out/private browser window, and confirm the README and source files are readable.
7. Paste the public repository URL into the YottaFlex Round 2 submission field. Review the URL carefully before submitting because the portal states that submission is final.

## Suggested Git commands

After creating the empty public repository on GitHub, replace `<repository-name>` below with its exact name:

```bash
git init
git add .
git commit -m "Build deterministic school bus routing and attendance simulator"
git branch -M main
git remote add origin https://github.com/omprakash-16/<repository-name>.git
git push -u origin main
```

Do not commit API keys, credentials, real student/guardian records, or the generated full-scale exports. This solution uses synthetic data only.
