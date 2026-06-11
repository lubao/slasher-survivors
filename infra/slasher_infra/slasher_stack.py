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
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
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
        # Fargate service behind an INTERNAL ALB. The ALB is not internet
        # facing; public access is fronted by CloudFront (VPC origin) below.
        # open_listener=False so the pattern does NOT add a 0.0.0.0/0 rule;
        # we scope ingress to the CloudFront managed prefix list instead.
        # CDK builds the backend image from the Dockerfile as an asset.
        #
        # NOTE: construct id is "Api" (not "Service"). Migrating an existing
        # public ALB to internal forces an ALB replacement, and the pattern's
        # single target group cannot briefly attach to two ALBs. A distinct
        # construct id provisions a fresh ALB+TG+listener+service and retires
        # the old set cleanly, with no DynamoDB impact.
        # ---------------------------------------------------------------- #
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Api",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            public_load_balancer=False,
            open_listener=False,
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

        # ---------------------------------------------------------------- #
        # CloudFront distribution in front of the internal ALB via a VPC
        # origin. CloudFront becomes the single public entry point; the ALB
        # stays private. The ALB security group only accepts traffic from the
        # CloudFront origin-facing managed prefix list.
        # ---------------------------------------------------------------- #
        cf_origin_facing = ec2.PrefixList.from_lookup(
            self, "CloudFrontOriginFacing",
            prefix_list_name="com.amazonaws.global.cloudfront.origin-facing",
        )
        service.load_balancer.connections.allow_from(
            cf_origin_facing, ec2.Port.tcp(80),
            "Allow CloudFront VPC origin to reach the internal ALB",
        )

        distribution = cloudfront.Distribution(
            self,
            "Cdn",
            comment="Slasher Survivors API (CloudFront -> internal ALB via VPC origin)",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.VpcOrigin.with_application_load_balancer(
                    service.load_balancer,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    http_port=80,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                # Dynamic API: never cache, and forward viewer query strings /
                # headers (minus Host) to the origin.
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            ),
        )

        CfnOutput(self, "CloudFrontUrl",
                  value=f"https://{distribution.distribution_domain_name}",
                  description="Public HTTPS endpoint (set the game's BACKEND_URL to this)")
        CfnOutput(self, "CloudFrontDomain",
                  value=distribution.distribution_domain_name)
        CfnOutput(self, "InternalAlbDnsName",
                  value=service.load_balancer.load_balancer_dns_name,
                  description="Internal ALB DNS (not publicly reachable)")
        CfnOutput(self, "TableName", value=table.table_name)
