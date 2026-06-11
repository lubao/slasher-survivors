"""Single-Region stack: DynamoDB + ECS Fargate (ALB) for the backend API."""
from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_logs as logs
from constructs import Construct

#: DynamoDB single-table name. Matches backend default (config.GAME_TABLE).
TABLE_NAME = "slasher-survivors"
#: Leaderboard GSI. Matches backend config.LEADERBOARD_INDEX.
LEADERBOARD_INDEX = "GSI1"
#: Container listen port (see backend/Dockerfile EXPOSE).
CONTAINER_PORT = 8000


class SlasherStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------- #
        # DynamoDB single table + leaderboard GSI
        # PK (S) / SK (S); GSI1PK (S) / GSI1SK (N). On-demand billing.
        # RETAIN on destroy so game data is never deleted by a stack teardown.
        # ---------------------------------------------------------------- #
        table = dynamodb.Table(
            self,
            "GameTable",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        table.add_global_secondary_index(
            index_name=LEADERBOARD_INDEX,
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.NUMBER),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ---------------------------------------------------------------- #
        # Networking — 2 AZs, single NAT gateway (cost-conscious for a demo).
        # ---------------------------------------------------------------- #
        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=1)

        cluster = ecs.Cluster(
            self, "Cluster", vpc=vpc, container_insights=True)

        log_group = logs.LogGroup(
            self,
            "ServiceLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------------------------------------------------------------- #
        # Fargate service behind a public ALB. CDK builds the backend image
        # from the Dockerfile as an asset and pushes it to the bootstrap ECR
        # repository, so no manual docker push/ordering is required.
        # ---------------------------------------------------------------- #
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            public_load_balancer=True,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("../backend"),
                container_port=CONTAINER_PORT,
                environment={
                    "GAME_TABLE": table.table_name,
                    "AWS_REGION": self.region,
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="slasher", log_group=log_group),
            ),
        )

        # ALB target-group health check hits the FastAPI /health endpoint.
        service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
        )

        # Least-privilege: task role gets read/write to the table + its indexes.
        table.grant_read_write_data(service.task_definition.task_role)

        CfnOutput(self, "AlbDnsName",
                  value=service.load_balancer.load_balancer_dns_name,
                  description="Public ALB DNS name for the backend API")
        CfnOutput(self, "TableName", value=table.table_name)
