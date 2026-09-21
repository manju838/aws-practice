"""SmartDocs AI as code.  Deploy in steps with:  scripts/40-cdk.sh deploy <4|5|6>

  phase 4  storage, layer, indexer + chat Lambdas, throttled HTTP API
  phase 5  + SNS alerts, CloudWatch alarms, dashboard, log retention
  phase 6  + API-key auth (Secrets Manager) and a presigned-upload endpoint
"""
from pathlib import Path

from aws_cdk import (
    CfnOutput, Duration, RemovalPolicy, Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
HANDLER = "lambda_function.lambda_handler"
NOT_CODE = ["__pycache__", "*.pyc"]


class SmartDocsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, project: str, phase: int,
                 chat_model_id: str, embed_model_id: str, temperature: str = "",
                 alert_email: str = "", layer_dir: str | Path | None = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.phase = phase
        layer_dir = Path(layer_dir) if layer_dir else ROOT / "layer" / "build"

        # ── storage ─────────────────────────────────────────────────
        bucket = s3.Bucket(
            self, "DocsBucket", versioned=True, enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True,   # learning project: `cdk destroy` leaves nothing behind
        )
        table = dynamodb.Table(
            self, "ConversationsTable",
            partition_key=dynamodb.Attribute(name="session_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="timestamp", type=dynamodb.AttributeType.NUMBER),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl", removal_policy=RemovalPolicy.DESTROY,
        )

        # ── auth secret (phase 6) ───────────────────────────────────
        secret = None
        if phase >= 6:
            secret = secretsmanager.Secret(
                self, "ApiKey", description=f"{project} API key (x-api-key header)",
                generate_secret_string=secretsmanager.SecretStringGenerator(exclude_punctuation=True, password_length=40),
                removal_policy=RemovalPolicy.DESTROY,
            )

        # ── lambdas ─────────────────────────────────────────────────
        layer = _lambda.LayerVersion(
            self, "FaissLayer", code=_lambda.Code.from_asset(str(layer_dir)),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.X86_64],
            description="faiss-cpu + PyMuPDF + numpy",
        )

        def log_group(name: str) -> logs.LogGroup:
            return logs.LogGroup(self, f"{name}Logs", retention=logs.RetentionDays.ONE_MONTH,
                                 removal_policy=RemovalPolicy.DESTROY)

        chat_env = {"DOCS_BUCKET": bucket.bucket_name, "CONVERSATIONS_TABLE": table.table_name,
                    "CHAT_MODEL_ID": chat_model_id, "EMBED_MODEL_ID": embed_model_id, "TEMPERATURE": temperature}
        if secret:
            chat_env["API_KEY_SECRET_ARN"] = secret.secret_arn

        indexer_logs, chat_logs = log_group("Indexer"), log_group("Chat")
        indexer = _lambda.Function(
            self, "Indexer", runtime=_lambda.Runtime.PYTHON_3_12, architecture=_lambda.Architecture.X86_64,
            handler=HANDLER, code=_lambda.Code.from_asset(str(ROOT / "src" / "indexer"), exclude=NOT_CODE),
            layers=[layer], timeout=Duration.seconds(300), memory_size=1024, log_group=indexer_logs,
            environment={"DOCS_BUCKET": bucket.bucket_name, "EMBED_MODEL_ID": embed_model_id},
        )
        chat = _lambda.Function(
            self, "Chat", runtime=_lambda.Runtime.PYTHON_3_12, architecture=_lambda.Architecture.X86_64,
            handler=HANDLER, code=_lambda.Code.from_asset(str(ROOT / "src" / "chat"), exclude=NOT_CODE),
            layers=[layer], timeout=Duration.seconds(30), memory_size=512, log_group=chat_logs,
            environment=chat_env,
        )

        # ── permissions: least privilege, one line each ─────────────
        bucket.grant_read(indexer); bucket.grant_put(indexer)         # read PDFs, write the index
        bucket.grant_read(chat)                                       # read the index
        table.grant_read_write_data(chat)
        titan = f"arn:aws:bedrock:*::foundation-model/{embed_model_id}"
        claude_models = [
            "arn:aws:bedrock:*::foundation-model/anthropic.*",                 # the models behind a profile
            f"arn:aws:bedrock:*:{self.account}:inference-profile/*",           # global./us./eu. profiles
        ]
        indexer.add_to_role_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=[titan]))
        chat.add_to_role_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=[titan, *claude_models]))
        if secret:
            secret.grant_read(chat)

        # Only .pdf files under docs/ trigger indexing. index/ must NEVER trigger it (infinite loop).
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(indexer),
            s3.NotificationKeyFilter(prefix="docs/", suffix=".pdf"),
        )

        # ── http api ────────────────────────────────────────────────
        http_api = apigwv2.HttpApi(
            self, "Api", api_name=f"{project}-api", create_default_stage=False,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],     # restrict to your frontend's domain in production
                allow_methods=[apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type", "x-api-key"],
            ),
        )
        stage = apigwv2.HttpStage(
            self, "ProdStage", http_api=http_api, stage_name="prod", auto_deploy=True,
            throttle=apigwv2.ThrottleSettings(rate_limit=5, burst_limit=10),   # public + paid model = cap it
        )
        http_api.add_routes(path="/chat", methods=[apigwv2.HttpMethod.POST],
                            integration=integrations.HttpLambdaIntegration("ChatIntegration", chat))

        CfnOutput(self, "ChatUrl", value=f"{stage.url}chat")
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "ChatLogGroup", value=chat_logs.log_group_name)

        # ── phase 6: auth + upload ──────────────────────────────────
        if phase >= 6:
            upload = _lambda.Function(
                self, "Upload", runtime=_lambda.Runtime.PYTHON_3_12, architecture=_lambda.Architecture.X86_64,
                handler=HANDLER, code=_lambda.Code.from_asset(str(ROOT / "src" / "upload"), exclude=NOT_CODE),
                timeout=Duration.seconds(10), memory_size=256, log_group=log_group("Upload"),
                environment={"DOCS_BUCKET": bucket.bucket_name, "API_KEY_SECRET_ARN": secret.secret_arn},
            )
            bucket.grant_put(upload, "docs/*")       # the presigned URL can only ever write under docs/
            secret.grant_read(upload)
            http_api.add_routes(path="/upload", methods=[apigwv2.HttpMethod.POST],
                                integration=integrations.HttpLambdaIntegration("UploadIntegration", upload))
            CfnOutput(self, "UploadUrl", value=f"{stage.url}upload")
            CfnOutput(self, "ApiKeySecretArn", value=secret.secret_arn)

        # ── phase 5: observability ──────────────────────────────────
        if phase >= 5:
            self._observability(project, http_api, chat, indexer, chat_logs, alert_email)

    def _observability(self, project, http_api, chat, indexer, chat_logs, alert_email):
        five = Duration.minutes(5)
        topic = sns.Topic(self, "AlertTopic", display_name=f"{project} alerts")
        if alert_email:
            topic.add_subscription(subs.EmailSubscription(alert_email))

        def api_metric(name, statistic="Sum"):
            return cw.Metric(namespace="AWS/ApiGateway", metric_name=name, statistic=statistic, period=five,
                             dimensions_map={"ApiId": http_api.http_api_id, "Stage": "prod"})

        def alarm(alarm_id, metric, threshold, description, periods=1):
            a = cw.Alarm(self, alarm_id, metric=metric, threshold=threshold, evaluation_periods=periods,
                         comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                         treat_missing_data=cw.TreatMissingData.NOT_BREACHING, alarm_description=description)
            a.add_alarm_action(cw_actions.SnsAction(topic))
            return a

        # p95, not the average: averages hide the slow tail that real users feel.
        alarm("ChatErrors", chat.metric_errors(period=five, statistic="Sum"), 1, "Chat Lambda threw errors")
        alarm("ChatSlowP95", chat.metric_duration(period=five, statistic="p95"), 15_000,
              "Chat p95 latency at or above 15 s (timeout is 30 s)", periods=2)
        alarm("IndexerErrors", indexer.metric_errors(period=five, statistic="Sum"), 1, "Indexer Lambda threw errors")
        alarm("Api5xx", api_metric("5xx"), 1, "API Gateway returned 5xx responses")

        dash = cw.Dashboard(self, "Dashboard", dashboard_name=f"{project}-overview")
        dash.add_widgets(
            cw.GraphWidget(title="Chat: invocations & errors", width=12,
                           left=[chat.metric_invocations(period=five, statistic="Sum"),
                                 chat.metric_errors(period=five, statistic="Sum")]),
            cw.GraphWidget(title="Chat: latency p50 / p95 / p99 (ms)", width=12,
                           left=[chat.metric_duration(period=five, statistic=s, label=s) for s in ("p50", "p95", "p99")]),
            cw.GraphWidget(title="API: requests, 4xx, 5xx", width=12,
                           left=[api_metric("Count"), api_metric("4xx"), api_metric("5xx")]),
            cw.GraphWidget(title="Indexer: invocations, errors", width=12,
                           left=[indexer.metric_invocations(period=five, statistic="Sum"),
                                 indexer.metric_errors(period=five, statistic="Sum")]),
            cw.LogQueryWidget(
                title="Slowest chat requests", width=24, log_group_names=[chat_logs.log_group_name],
                query_lines=[
                    "filter @message like /Request complete/",
                    'parse @message /"duration_ms": (?<duration_ms>[0-9]+)/',
                    'parse @message /"session_id": "(?<session>[^"]*)"/',
                    'parse @message /"chunks": (?<chunks>[0-9]+)/',
                    "sort duration_ms desc | limit 10",
                    "fields @timestamp, session, duration_ms, chunks",
                ]),
        )
        CfnOutput(self, "DashboardName", value=dash.dashboard_name)
        CfnOutput(self, "AlertTopicArn", value=topic.topic_arn)
