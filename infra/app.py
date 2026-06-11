#!/usr/bin/env python3
"""CDK app entrypoint for Slasher Survivors.

Task 5 — single-Region (us-west-1) infrastructure. Multi-Region (Task 6) will
add a second stack instance in ap-east-2 plus a DynamoDB Global Table and
Route 53 latency routing.
"""
import aws_cdk as cdk

from slasher_infra.slasher_stack import SlasherStack

# Primary Region for Task 5. The account is pinned to the `game` account so a
# wrong-profile deploy fails fast instead of provisioning in the wrong account.
# Always run cdk with `--profile game`.
PRIMARY_REGION = "us-west-1"
ACCOUNT = "253988640130"

app = cdk.App()

SlasherStack(
    app,
    "SlasherSurvivors-UsWest1",
    env=cdk.Environment(account=ACCOUNT, region=PRIMARY_REGION),
    description="Slasher Survivors single-Region backend (DynamoDB, ECS Fargate, ALB).",
)

app.synth()
