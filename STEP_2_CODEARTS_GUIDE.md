# Step 2 — Prepare the project in Huawei CodeArts

This is a **guided setup checkpoint**, not proof that CodeArts or Huawei Cloud is already connected. Complete each item in your own competition account and save the evidence requested below.

## What this stage accomplishes

- Preserve the current tested local prototype as a baseline.
- Import the source into the CodeArts repository provided by the competition.
- Use CodeArts Code Intelligent Agent for a documented requirements review.
- Record prompts, generated recommendations, commits, test output, and human review.
- Keep credentials, local databases, and private data out of the repository.

## Official competition links (from the competition material you shared)

- CodeArts Code Intelligent Agent download/use guide: https://developer.huaweicloud.com/codeartsco.html?source=dmzntcompetition
- AI developer space / DevStation: https://devstation.developer.huaweicloud.com/aidevspace?utm_source=competition&utm_medium=ict&utm_campaign=innovation
- AI developer space landing page: https://aidevbp.developer.huaweicloud.com/
- Skills auto-deployment case study: https://gitcode.com/weixin_43883336/auto-deploy/blob/main/auto-deploy-case-study.md

Use the exact entry point and services permitted by your team/competition account. Resource names, quotas, availability, and the current user interface must be confirmed inside that account. Do not paste secrets into prompts.

## A. Before importing

1. Extract this ZIP to a normal project folder, such as `D:\Projects\campus_memory_ai`.
2. Run the local project and confirm the home page and health endpoint work before changing anything. See `STEP_1_START_HERE.md`.
3. In PowerShell, open the project root and run:

```powershell
git --version
git status --short
```

If Git is not installed, install Git for Windows from the official Git website before proceeding.

4. Inspect the files to be committed. Do not commit `.env`, API keys, local `.db` files, actual student submissions, unlicensed source material, or passwords. The supplied `.gitignore` excludes local secrets and databases.

## B. Create a local baseline commit

Run these commands from the project root:

```powershell
git init
git branch -M main
git add .
git status --short
```

Review the status output carefully. If it lists `.env`, `*.db`, secret files, or personal data, stop and fix `.gitignore` before continuing. If only expected source and documentation files are listed, commit the baseline:

```powershell
git commit -m "chore: establish Campus Memory AI prototype baseline"
```

If Git asks for your identity, set a team-approved name and email using `git config user.name` and `git config user.email`. Do not use another person's identity without permission.

## C. Connect to the CodeArts repository

1. Sign in to your competition account and open its CodeArts code repository service.
2. Create an appropriately named repository such as `campus-memory-ai`. Keep it private during setup unless the competition instructions explicitly require otherwise. The public open-source release should happen only after the team agrees on the code licence and the secret/dependency audit is complete.
3. Copy the repository's HTTPS or SSH clone URL from CodeArts.
4. Connect and push (replace the placeholder; do not paste passwords or access tokens into chat):

```powershell
git remote add origin <YOUR_CODEARTS_REPOSITORY_URL>
git push -u origin main
```

If the repository already has a README or initial commit, do not force-push. Stop and merge/clone according to the CodeArts instructions instead.

## D. First CodeArts Agent task

Open `CODEARTS_FIRST_TASK_PROMPT.md` and paste that prompt into the CodeArts Code Intelligent Agent. The prompt asks for a requirements review first and explicitly tells the agent not to rewrite the application yet. Save the actual task, agent response, and any screenshots/logs.

Then run the test commands in the agent's environment:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
python -m compileall -q app ../scripts
node --check app/static/app.js
```

Record real results in `evidence/CODEARTS_WORK_LOG_TEMPLATE.md`. Do not copy a local test result into the CodeArts log as though CodeArts ran it.

## E. What counts as evidence

Save the following from the real session:

- repository name/URL (do not share credentials), branch and commit hash;
- CodeArts Agent task prompt and response;
- build/test command, timestamp, and complete pass/fail output;
- files changed by the agent and a diff/review result;
- human review, requirement IDs affected, and regression-test result.

The existence of this guide is not itself evidence of CodeArts usage. Complete the template only after performing the real actions.

## Stop point for this stage

Do not deploy to the public internet yet. First verify the CodeArts repo contains the source, the baseline tests pass there, and the first Agent review has been recorded. Then share a screenshot of the repository/Agent result with credentials hidden, or paste the sanitized output, and we will proceed to the RDS/Redis/model-service stage.
