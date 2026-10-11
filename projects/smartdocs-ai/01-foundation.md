<!-- markdownlint-disable-file -->
# Phase 1: Foundation

## Why this phase exists

Almost every failure in the first attempt was a foundation problem: wrong credentials, a model the account could not call,
leftover resources with clashing names. This phase makes those impossible before any real building starts. It ends
with proof that this account can call the exact Claude model the project will use.

## Steps

### 1. Tools

You need: `aws` (v2), `uv`, Node.js with the CDK CLI, and Git Bash on Windows. Docker is optional (site preview only).

```bash
aws --version
uv --version
node --version && npm install -g aws-cdk && cdk --version
```

Why uv: it installs Python, creates the environment, locks versions and builds the Lambda layer, so nothing else is needed.
See [conventions](../../docs/README.md).

### 2. Credentials

Work as an IAM admin user, never root. Confirm who you are:

```bash
# aws configure                       # region: ap-south-2, output: json
export AWS_PROFILE=personal           # Saved AWS credentials as profiles, so loading the right credentials, see personal-notes/AWS General Notes.md
aws sts get-caller-identity
```

Real companies use IAM Identity Center with short-lived credentials instead of long-lived access keys; for a personal
account an access key on a non-root admin user is acceptable, but keep it out of git.

### 3. Project config and Python environment

```bash
cd projects/smartdocs-ai
cp config.env.example config.env     # config.env.example is pushed to Github while config.env is always local, any forced env variable changes made based on each user wont be accidentally commited to Github
uv sync
uv run pytest                        # should report 49 passed, with no AWS access
```

`config.env` is git-ignored and excluded from the site. The account ID is never written down; scripts look it up.

### 4. Publish the site early

Doing this now means every later phase can be documented into a live site. Follow [Publishing and previewing the site](../../docs/publishing.md):
set `url` and `baseurl` in `_config.yml`, push, and enable Pages.

### 5. Check Claude and Titan access

Run the following:
```bash
tools/capture.sh smartdocs-ai 10-bedrock-access bash scripts/10-check-bedrock.sh
```

The script lists your Anthropic inference profiles, calls every model in config.env's `CANDIDATE_MODELS` through the Converse API, and confirms Titan returns a 1024-number vector. It fails loudly if `CHAT_MODEL_ID` is not callable.
* Lambda rola has no Marketplace permissions, so it can't subscribe to a Bedrock model by itself.
* AWS Marketplace subscription needs "Switching to Invoice" mode for payment, using Indian cards or UPI doesnt work as Indian rules dont allow true "Pay as you Go" permissions, i.e money cany be autodebited on the go, so raise a request to change payment method to "Bill by Invoice" in AWS Support. This is the most likely reason if you get `INVALID_PAYMENT_INSTRUMENT` error.

### 6. Clean slate

The first attempt used the same resource names (`smartdocs-...`). Delete it so the rebuild starts empty:

```bash
bash scripts/90-teardown-manual.sh     # lists exactly what it will delete and asks first
```

If nothing exists it says "not found" and moves on. Safe to run any time.

### 7. Bootstrap CDK (once per account and region)

```bash
bash scripts/40-cdk.sh bootstrap
```

This creates a staging bucket and roles that CDK uses to upload Lambda code and the layer. It is needed once and lives outside your stack.

## Verify

* `aws sts get-caller-identity` shows your admin user, not root.
* `10-check-bedrock.sh` ends with "Phase 1 complete".
* `uv run pytest` passes.
* The site is live and shows the SmartDocs tab.

## Results

TODO(result): which candidate models worked and which failed, from [results/10-bedrock-access.txt](results/10-bedrock-access.txt).

TODO(result): the model ID chosen and why.


## Gotchas and lessons

* `cdk` "81 feature flags are not configured" is an informational message from newer CDK versions, not an error.
* On Windows, scripts must keep LF line endings; `.gitattributes` in this repo enforces it.
