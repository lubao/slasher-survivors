# infra — AWS CDK

AWS CDK (Python) infrastructure for Slasher Survivors.

- **Task 5 (done):** single-Region stack in `us-west-1`.
- **Task 6 (planned):** second Region `ap-east-2`, DynamoDB Global Table,
  Route 53 latency routing + health-check failover.

## Stack: `SlasherSurvivors-UsWest1`

| Resource | Detail |
|----------|--------|
| DynamoDB table `slasher-survivors` | `PK`/`SK` (String), GSI `GSI1` (`GSI1PK` S / `GSI1SK` N), PAY_PER_REQUEST, PITR on, **RETAIN** on stack delete |
| VPC | 2 AZs, 1 NAT gateway |
| ECS Fargate | cluster + service, 1 task, 0.25 vCPU / 512 MB |
| Container image | built from `../backend/Dockerfile` as a CDK asset (pushed to the bootstrap ECR repo) |
| Application Load Balancer | public, listener :80 → container :8000, target-group health check `GET /health` (expects `200`) |
| CloudWatch Logs | service log group, 1-week retention, stream prefix `slasher` |
| IAM | task execution role + task role (least-privilege read/write to the table + indexes) |

The task role grants DynamoDB access scoped to the table and its indexes; the
container reads `GAME_TABLE` and `AWS_REGION` from its environment.

## Prerequisites

- Docker running (CDK builds the backend image locally during deploy)
- Node.js (the `aws-cdk` CLI is installed locally here via `npm install`)
- Python 3 + the `.venv` below
- AWS credentials for the **`game`** profile (account `253988640130`)

> The stack account is pinned to `253988640130` in `app.py`, so a deploy with
> the wrong profile fails fast. Always pass `--profile game`.

## Usage

```bash
cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install            # provides the aws-cdk CLI (npx cdk ...)

# one-time per account/Region
npx cdk bootstrap aws://253988640130/us-west-1 --profile game

npx cdk synth  --profile game
npx cdk deploy --profile game --require-approval never
```

### Outputs

- `AlbDnsName` / `ServiceURL` — public ALB endpoint for the API
- `TableName` — `slasher-survivors`

Verify after deploy:

```bash
curl http://<AlbDnsName>/health        # {"status":"ok"}
curl http://<AlbDnsName>/leaderboard
```

## Teardown

```bash
npx cdk destroy --profile game
```

The DynamoDB table has `RemovalPolicy.RETAIN`, so it (and its data) **survives**
`cdk destroy` and must be deleted manually if no longer needed.

## Notes / cost

While running, the stack incurs ongoing cost (NAT gateway, ALB, Fargate task,
per-request DynamoDB). Destroy it when not in use. The ALB exposes the API
publicly and unauthenticated, matching the game's public-API design.
