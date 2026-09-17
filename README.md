# GitHub API automation

CLI for `doitupsolutions810-crow`:

- list every repo + latest Actions conclusion
- `workflow_dispatch` against a named workflow

## Python (PAT or GitHub App)

```bash
export GITHUB_TOKEN=ghp_...
python3 ghctl.py inventory
python3 ghctl.py dispatch doitupsolutions810-crow/control12-workspace commercial-ci.yml --ref main --inputs '{"mode":"lab"}'
```

GitHub App:

```bash
export GITHUB_APP_ID=123456
export GITHUB_APP_INSTALLATION_ID=149956112
export GITHUB_APP_PRIVATE_KEY_PATH=./app.pem
python3 ghctl.py inventory
```

Fails closed if no credentials.

## Node / Octokit

```bash
npm install
export GITHUB_TOKEN=ghp_...
npm run inventory
```
