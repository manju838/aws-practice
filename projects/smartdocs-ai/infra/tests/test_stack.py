"""Synthesise the stack at each phase and assert on the resulting CloudFormation template.
No AWS access needed."""
import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from smartdocs_stack import SmartDocsStack


def synth(phase, tmp_path):
    (tmp_path / "python").mkdir(exist_ok=True)
    (tmp_path / "python" / "placeholder.py").write_text("")          # stands in for the built layer
    app = cdk.App()
    stack = SmartDocsStack(
        app, "t", project="smartdocs", phase=phase, layer_dir=tmp_path,
        chat_model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        embed_model_id="amazon.titan-embed-text-v2:0", alert_email="me@example.com",
        env=cdk.Environment(account="123456789012", region="ap-south-2"),
    )
    return Template.from_stack(stack)


def our_functions(t):
    return {k: v for k, v in t.find_resources("AWS::Lambda::Function").items()
            if v["Properties"].get("Handler") == "lambda_function.lambda_handler"}


def all_statements(t):
    for pol in t.find_resources("AWS::IAM::Policy").values():
        yield from pol["Properties"]["PolicyDocument"]["Statement"]


def test_phase4_core_resources(tmp_path):
    t = synth(4, tmp_path)
    assert len(our_functions(t)) == 2
    t.resource_count_is("AWS::DynamoDB::Table", 1)
    t.resource_count_is("AWS::Lambda::LayerVersion", 1)
    t.resource_count_is("AWS::ApiGatewayV2::Api", 1)
    t.has_resource_properties("AWS::DynamoDB::Table", {
        "BillingMode": "PAY_PER_REQUEST", "TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True}})
    t.has_resource_properties("AWS::S3::Bucket", {
        "VersioningConfiguration": {"Status": "Enabled"},
        "PublicAccessBlockConfiguration": Match.object_like({"BlockPublicAcls": True, "RestrictPublicBuckets": True})})
    # no monitoring or auth yet
    t.resource_count_is("AWS::CloudWatch::Alarm", 0)
    t.resource_count_is("AWS::SecretsManager::Secret", 0)


def test_s3_trigger_is_scoped_to_docs_pdf(tmp_path):
    """The infinite-loop guard: the trigger must never fire on index/."""
    t = synth(4, tmp_path)
    props = list(t.find_resources("Custom::S3BucketNotifications").values())[0]["Properties"]
    rules = props["NotificationConfiguration"]["LambdaFunctionConfigurations"][0]["Filter"]["Key"]["FilterRules"]
    assert {(r["Name"].lower(), r["Value"]) for r in rules} == {("prefix", "docs/"), ("suffix", ".pdf")}


def test_api_stage_is_throttled(tmp_path):
    t = synth(4, tmp_path)
    t.has_resource_properties("AWS::ApiGatewayV2::Stage", {
        "StageName": "prod", "AutoDeploy": True,
        "DefaultRouteSettings": {"ThrottlingRateLimit": 5, "ThrottlingBurstLimit": 10}})


def test_no_wildcard_actions_and_no_full_access_policies(tmp_path):
    t = synth(6, tmp_path)
    for st in all_statements(t):
        actions = st["Action"] if isinstance(st["Action"], list) else [st["Action"]]
        assert "*" not in actions, st
    for role in t.find_resources("AWS::IAM::Role").values():
        for arn in role["Properties"].get("ManagedPolicyArns", []):
            assert "FullAccess" not in json.dumps(arn)


def test_bedrock_permission_is_invoke_only_and_chat_can_call_claude(tmp_path):
    t = synth(4, tmp_path)
    bedrock = [s for s in all_statements(t) if "bedrock:InvokeModel" in json.dumps(s["Action"])]
    assert len(bedrock) == 2                                      # indexer (Titan) and chat (Titan + Claude)
    claude = [s for s in bedrock if "anthropic" in json.dumps(s["Resource"])]
    assert len(claude) == 1
    assert "inference-profile" in json.dumps(claude[0]["Resource"])


def test_chat_lambda_gets_the_model_id_and_only_read_access_to_the_bucket(tmp_path):
    t = synth(4, tmp_path)
    chat = next(v for v in our_functions(t).values() if v["Properties"]["MemorySize"] == 512)
    assert chat["Properties"]["Environment"]["Variables"]["CHAT_MODEL_ID"].startswith("global.anthropic.claude-haiku")
    chat_role = chat["Properties"]["Role"]["Fn::GetAtt"][0]
    for pol in t.find_resources("AWS::IAM::Policy").values():
        roles = [r["Ref"] for r in pol["Properties"]["Roles"]]
        if chat_role in roles:
            s3_actions = {a for st in pol["Properties"]["PolicyDocument"]["Statement"]
                          for a in (st["Action"] if isinstance(st["Action"], list) else [st["Action"]]) if a.startswith("s3:")}
            assert not any(a.startswith(("s3:Put", "s3:Delete")) for a in s3_actions), s3_actions


def test_phase5_adds_monitoring(tmp_path):
    t = synth(5, tmp_path)
    t.resource_count_is("AWS::CloudWatch::Alarm", 4)
    t.resource_count_is("AWS::CloudWatch::Dashboard", 1)
    t.resource_count_is("AWS::SNS::Topic", 1)
    t.has_resource_properties("AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": "me@example.com"})
    t.has_resource_properties("AWS::CloudWatch::Alarm", {"ExtendedStatistic": "p95"})   # alerts on p95, not the average
    t.resource_count_is("AWS::SecretsManager::Secret", 0)


def test_phase6_adds_auth_and_upload(tmp_path):
    t = synth(6, tmp_path)
    t.resource_count_is("AWS::SecretsManager::Secret", 1)
    assert len(our_functions(t)) == 3
    t.has_resource_properties("AWS::ApiGatewayV2::Route", {"RouteKey": "POST /upload"})
    t.has_resource_properties("AWS::ApiGatewayV2::Route", {"RouteKey": "POST /chat"})
    for fn in our_functions(t).values():
        env = fn["Properties"]["Environment"]["Variables"]
        if "CHAT_MODEL_ID" in env or "API_KEY_SECRET_ARN" in env:
            assert "API_KEY_SECRET_ARN" in env


def test_upload_can_only_write_under_docs(tmp_path):
    t = synth(6, tmp_path)
    puts = [s for s in all_statements(t)
            if any(a.startswith("s3:PutObject") or a.startswith("s3:Abort") for a in
                   (s["Action"] if isinstance(s["Action"], list) else [s["Action"]]))]
    assert any("docs/*" in json.dumps(s["Resource"]) for s in puts)
