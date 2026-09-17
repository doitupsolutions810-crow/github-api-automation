# Create the CONTROL12 GitHub App

Grok cannot mint a GitHub App private key for you. Do this once in the browser.

1. Open https://github.com/settings/apps/new
2. Name: `control12-authority`
3. Homepage: https://github.com/doitupsolutions810-crow/capability-authority
4. Webhook: uncheck Active (CLI uses installation tokens, not webhooks)
5. Repository permissions:
   - Actions: Read and write (dispatch + read runs)
   - Contents: Read
   - Metadata: Read
   - Workflows: Read and write (optional, only if dispatching new workflow files)
6. Where can this App be installed: Only on this account
7. Create the App
8. Record App ID
9. Generate a private key and download the PEM (do not commit it)
10. Install the App on:
    - control12-workspace
    - capability-authority
    - trinity-core
    - github-api-automation
11. From the install URL, copy the installation id (also visible as `149956112` if you reuse the existing Grok GitHub connector install)

Then on the machine that runs Trinity / ghctl:

```bash
export GITHUB_APP_ID=...
export GITHUB_APP_INSTALLATION_ID=...
export GITHUB_APP_PRIVATE_KEY_PATH=$HOME/.secrets/control12-authority.pem
export PRODUCTION=1
python3 ghctl.py inventory
```

Never put the PEM in a git repo. Repo secrets or a local file outside the tree only.
