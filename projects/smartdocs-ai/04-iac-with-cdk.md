# Phase 4: Infrastructure as code with CDK

| | |
| --- | --- |
| **Time budget** | 90 min |
| **Actual time** | ⏳ |
| **Cost** | about $0 |
| **Status** | ⬜ Not started |

## Why this phase exists

Everything so far was a sequence of commands typed in a particular order. If the account were wiped, rebuilding would mean
remembering that order. Infrastructure as code turns the whole system into a file that lives in git, can be reviewed, and creates or destroys everything with one command.

```
Python (infra/smartdocs_stack.py) ──cdk synth──► CloudFormation template ──cdk deploy──► real resources
```

CDK has three nested layers. A **construct** is one resource or a small group of them (a bucket, a function). A **stack** is a set of constructs deployed
and deleted together. An **app** (`infra/app.py`) holds the stacks and is what `cdk` starts from.

## Steps

### 1. Tear down the hand-built version

```bash
bash scripts/90-teardown-manual.sh
```

Not strictly required (CDK names its own resources), but it proves the point: after this, the stack must be able to rebuild everything alone.

### 2. Read the stack

`infra/smartdocs_stack.py` defines the same architecture as Phases 2 and 3. Compare it with the scripts:

| Scripts (Phases 2-3) | CDK |
| --- | --- |
| `20-create-bucket.sh` | `s3.Bucket(...)`: versioned, no public access, TLS only |
| `21-create-iam-role.sh` | `bucket.grant_read(chat)`: CDK writes the policy for you |
| `22-build-layer.sh` publish step | `LayerVersion(code=from_asset(...))`: CDK uploads it |
| `24-attach-s3-trigger.sh` | `bucket.add_event_notification(...)` with prefix and suffix |
| `32-create-api.sh` | `HttpApi` plus a throttled `HttpStage` |

The grants are the biggest change: `table.grant_read_write_data(chat)` produces exactly the right IAM statement, where the scripts spelled each one out.

### 3. Run the stack's tests

```bash
uv run pytest infra
```

These synthesize the stack at each phase and assert on the template: the S3 trigger is limited to `docs/*.pdf`, the API stage is throttled,
no policy has a wildcard action or a `FullAccess` policy, and the chat function can read the bucket but not write it. No AWS access is needed.

### 4. Synthesize, diff, deploy

```bash
bash scripts/40-cdk.sh synth 4        # compile Python to a CloudFormation template; deploys nothing
bash scripts/40-cdk.sh diff 4         # on the first run, everything shows as new
tools/capture.sh smartdocs-ai 40-cdk-deploy bash scripts/40-cdk.sh deploy 4
```

CDK asks you to approve the IAM changes before it creates them. `cdk diff` is how you review those changes beforehand, and in a company it is run before every production deploy.
The layer built in Phase 2 (`layer/build`) is packaged and uploaded by CDK. Outputs, including the API URL, are saved to `build/cdk-outputs.json`.

### 5. Prove it works

The new stack has its own, empty, auto-named bucket, so upload the sample and ask the same questions:

```bash
tools/capture.sh smartdocs-ai 41-upload-cdk bash scripts/41-upload-sample-cdk.sh
tools/capture.sh smartdocs-ai 42-chat-cdk bash scripts/33-test-chat.sh --cdk
```

### 6. Prove it is repeatable

```bash
bash scripts/40-cdk.sh destroy        # deletes everything, including the bucket contents
bash scripts/40-cdk.sh deploy 4       # and back again
```

## Verify

* `cdk deploy` ends with Outputs (`ChatUrl`, `BucketName`) and no errors.
* `33-test-chat.sh --cdk` prints "all checks passed".
* After `destroy`, the CloudFormation console shows no stack and the bucket is gone.

## Results

TODO(result): the `cdk diff` summary on a first deploy, and how many resources the stack created ([results/40-cdk-deploy.txt](results/40-cdk-deploy.txt)).

TODO(result): time for a first `deploy`, and for a `destroy`.

TODO(result): roughly how many lines of Python replace how many lines of shell, for the same architecture.

## Gotchas and lessons

* The stack needs `layer/build` to exist, so Phase 2 step 3 must have been run on this machine. `40-cdk.sh` checks and tells you.
* No physical names are hardcoded in the stack. CDK generates them, so a destroyed-and-recreated stack never collides with a leftover.
* `auto_delete_objects` and `RemovalPolicy.DESTROY` are right for a learning project and wrong for production data. Production uses `RETAIN`.
* TODO(result): first-deploy errors and fixes.
