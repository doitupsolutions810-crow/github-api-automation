#!/usr/bin/env node
import { Octokit } from "@octokit/rest";

function token() {
  const t = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (!t) {
    console.error("FAIL_CLOSED: set GITHUB_TOKEN (or use ghctl.py for GitHub App JWT)");
    process.exit(2);
  }
  return t;
}

const octokit = new Octokit({ auth: token(), userAgent: "ghctl-octokit" });
const { data: me } = await octokit.rest.users.getAuthenticated();
const repos = await octokit.paginate(octokit.rest.search.repos, {
  q: `user:${me.login}`,
  per_page: 100,
});

const out = [];
for (const repo of repos) {
  const [owner, name] = repo.full_name.split("/");
  let workflow = null;
  try {
    const { data } = await octokit.rest.actions.listWorkflowRunsForRepo({
      owner,
      repo: name,
      per_page: 1,
    });
    const run = data.workflow_runs[0];
    if (run) {
      workflow = {
        name: run.name,
        conclusion: run.conclusion || run.status,
        html_url: run.html_url,
        updated_at: run.updated_at,
      };
    }
  } catch (err) {
    workflow = { conclusion: `error:${err.message}` };
  }
  out.push({
    full_name: repo.full_name,
    private: repo.private,
    html_url: repo.html_url,
    workflow,
  });
}

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ login: me.login, count: out.length, repos: out }, null, 2));
} else {
  console.log(`login=${me.login} repos=${out.length}`);
  for (const row of out) {
    const c = row.workflow?.conclusion || "-";
    console.log(`${String(c).padEnd(16)} ${row.full_name}`);
  }
}
