#!/usr/bin/env python3
"""CDK entry point. Context values come from scripts/40-cdk.sh (which reads config.env)."""
import os

import aws_cdk as cdk

from smartdocs_stack import SmartDocsStack

app = cdk.App()
ctx = lambda key, default="": app.node.try_get_context(key) or default   # noqa: E731

project = ctx("project", "smartdocs")
SmartDocsStack(
    app, f"{project}-stack",
    project=project,
    phase=int(ctx("phase", "4")),
    chat_model_id=ctx("chat_model", "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
    embed_model_id=ctx("embed_model", "amazon.titan-embed-text-v2:0"),
    temperature=ctx("temperature"),
    alert_email=ctx("alert_email"),
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                        region=os.getenv("CDK_DEFAULT_REGION", "ap-south-2")),
)
cdk.Tags.of(app).add("project", project)     # per-project cost breakdown in Cost Explorer
app.synth()
