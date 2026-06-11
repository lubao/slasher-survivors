# infra — AWS CDK (Task 5–7)

Multi-Region infrastructure for Slasher Survivors. **Not yet implemented** —
scheduled for Task 5–7 once AWS credentials are provided.

Planned stacks:

- **Networking + service stack** (per Region): VPC, ECS Fargate service, ALB,
  ECR repository, CloudWatch Log Group, IAM task/exec roles.
- **DynamoDB Global Table**: single table with `GSI1` leaderboard index,
  replicated across `us-west-1` (primary) and `ap-east-2` (Taipei).
- **Route 53**: latency-based routing + health checks across both Region ALBs
  for nearest-write routing and cross-Region failover.

Target Regions: `us-west-1` (primary), `ap-east-2` (secondary).
