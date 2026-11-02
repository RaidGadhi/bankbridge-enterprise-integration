# Publish the repository to GitHub

The archive contains **source files and no Git credentials, secrets or `.git` history**. This avoids uploading accidental machine-specific state. You can publish the source in a new public repository when ready.

## Git + GitHub CLI (recommended)

1. Extract `bankbridge-enterprise-integration.zip` onto your own machine.
2. `cd bankbridge-enterprise-integration`
3. Test locally: `bash scripts/demo.sh`, or `python -m pytest -q` if dependencies are installed.
4. Confirm `.env` was not added: `git status --short` after initializing. `.gitignore` excludes it.
5. Authenticate: `gh auth login`.
6. Publish:

```bash
git init -b main
git add .
git commit -m "Initial BankBridge integration prototype"
gh repo create bankbridge-enterprise-integration --public --source=. --remote=origin --push
```

## Browser upload alternative

Create a new public repo named `bankbridge-enterprise-integration` on GitHub, then upload the files/folders (not the ZIP itself). Ensure README.md is at the repository root, and `.env` is never uploaded.

## After publishing

* Open GitHub Actions and inspect whether `python-tests` and `jms-build` both succeed. The Java build has not yet been verified locally.
* Add a screenshot of your **actual** successful smoke test to `docs/evidence/` if you wish.
* Only add evidence of real MQ/ACE/OpenShift deployments once performed.
* Add real trusted images/architecture diagrams only if useful. Mermaid in the README renders automatically on GitHub.
* Never disclose employer data, integration secrets, or genuine banking information.
