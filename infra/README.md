# infra — AWS CDK

AWS CDK (Python) infrastructure for Slasher Survivors.

- **Task 5 (done):** single-Region stack in `us-west-1`, fronted by CloudFront.
- **Task 6 (planned):** second Region `ap-east-2`, DynamoDB Global Table,
  Route 53 latency routing + health-check failover.

## Architecture

```
Internet ──HTTPS──> CloudFront ──VPC origin──> internal ALB ──> ECS Fargate ──> DynamoDB
                    (public)                   (private subnets, not public)        │
                                                                                    └─> Cognito (signup/login)
```

CloudFront is the single public entry point. The ALB is **internal** (private
subnets) and only accepts traffic from the CloudFront managed prefix list
`com.amazonaws.global.cloudfront.origin-facing`, reached via a CloudFront
**VPC origin**. Auth is handled by a **Cognito User Pool**; the backend proxies
signup/login and verifies ID tokens on `POST /scores`.

## Stack: `SlasherSurvivors-UsWest1`

| Resource | Detail |
|----------|--------|
| CloudFront distribution | public HTTPS, redirect-to-HTTPS, `ALLOW_ALL` methods (API needs POST), caching disabled (dynamic), `ALL_VIEWER_EXCEPT_HOST_HEADER` origin request policy |
| CloudFront VPC origin | targets the internal ALB over HTTP:80 |
| Cognito User Pool | email sign-in, self sign-up, `nickname` attribute, password policy (≥8, lower+digit), `RemovalPolicy.DESTROY` |
| Pre-signup Lambda | auto-confirms users + auto-verifies email (no emailed code) |
| Cognito app client | public (no secret), `USER_PASSWORD_AUTH` + SRP, 8h access/id tokens |
| DynamoDB table `slasher-survivors` | `PK`/`SK` (String), GSI `GSI1` (`GSI1PK` S / `GSI1SK` N), PAY_PER_REQUEST, PITR on, **RETAIN** on stack delete |
| VPC | 2 AZs, 1 NAT gateway |
| ECS Fargate | cluster + service, 1 task, 0.25 vCPU / 512 MB (construct id `Api`); env `GAME_TABLE`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_REGION` |
| Container image | built from `../backend/Dockerfile` as a CDK asset |
| Internal ALB | `scheme: internal`, listener :80 → container :8000, health check `GET /health`; SG ingress only from the CloudFront prefix list |
| CloudWatch Logs | service log group, 1-week retention, stream prefix `slasher` |
| IAM | task execution role + task role (least-privilege: DynamoDB read/write + `cognito-idp` signup/login on the pool) |

## Prerequisites

- Docker running (CDK builds the backend image locally during deploy)
- Node.js (the `aws-cdk` CLI is installed locally here via `npm install`)
- Python 3 + the `.venv` below
- AWS credentials for the **`game`** profile (account `253988640130`)

> The stack account is pinned to `253988640130` in `app.py`, so a deploy with
> the wrong profile fails fast. Always pass `--profile game`.
>
> CloudFront VPC origins require `aws-cdk-lib >= 2.258`.

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

- `CloudFrontUrl` — public HTTPS endpoint (set the game's `BACKEND_URL` to this)
- `CloudFrontDomain` — the CloudFront domain name
- `InternalAlbDnsName` — internal ALB DNS (not publicly reachable; for debugging)
- `TableName` — `slasher-survivors`
- `UserPoolId` / `UserPoolClientId` — Cognito identifiers (injected into the task)

Verify after deploy (CloudFront can take 5–15 min to propagate):

```bash
curl https://<CloudFrontDomain>/health        # {"status":"ok"}
curl https://<CloudFrontDomain>/leaderboard
```

## Migration note (public ALB → internal + CloudFront)

Switching an existing internet-facing ALB to `internal` forces an ALB
replacement, and the ECS pattern's single target group cannot briefly attach to
two ALBs. To avoid that conflict the load-balanced service uses the construct id
`Api` (not `Service`), so CloudFormation provisions a fresh ALB + target group +
listener + service and retires the old set in one deploy — with no DynamoDB
impact.

## Teardown

```bash
npx cdk destroy --profile game
```

The DynamoDB table has `RemovalPolicy.RETAIN`, so it (and its data) **survives**
`cdk destroy` and must be deleted manually if no longer needed.

## Notes / cost

While running, the stack incurs ongoing cost (CloudFront requests + data
transfer, NAT gateway, ALB, Fargate task, per-request DynamoDB). Destroy it when
not in use. CloudFront is the only public surface; the ALB is private.
