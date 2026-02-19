# Deployment Guide

This guide covers deployment of the Nova Sonic Healthcare Call Center using Amazon Bedrock AgentCore.

## Prerequisites

- **AWS Account** with administrative access or appropriate IAM permissions
- **AWS CLI** configured (`aws sts get-caller-identity` to verify)
- **AWS CDK** installed (`npm install -g aws-cdk`)
- **Node.js** 20+
- **Python** 3.12+ (3.13 recommended)
- **pip** — Python package manager (included with Python)
- **Docker** running (for AgentCore container build)


## Deployment Steps

### Phase 1: Deploy Infrastructure

```bash
cd infrastructure

# Create a virtual environment and install CDK dependencies
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Bootstrap CDK (one-time per account/region)
cdk bootstrap

# Deploy the stack
cdk deploy --require-approval never
```

This deploys:
- **AgentCore Runtime** — containerized BidiAgent with Nova Sonic 2
- **Cognito User Pool & Identity Pool** — user authentication
- **DynamoDB Tables** — Patients, Appointments, AvailableSlots
- **SNS Topic** — escalation notifications
- **Lambda** — data seeding function

### Phase 2: Note CDK Outputs

After deployment, note these outputs for frontend configuration:

```bash
aws cloudformation describe-stacks \
  --stack-name NovaHealthcareStack \
  --query 'Stacks[0].Outputs'
```

Key outputs:
- `CognitoUserPoolId`
- `CognitoUserPoolClientId`
- `CognitoIdentityPoolId`
- `AgentCoreRuntimeArn`

### Phase 3: Create Cognito Test User

The CDK stack auto-creates a test user. If you need to create one manually:

```bash
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name NovaHealthcareStack \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' \
  --output text)

aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --user-attributes Name=email,Value=testuser@example.com Name=email_verified,Value=true \
  --temporary-password TempPass123!

aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --password TestUser123! \
  --permanent
```

**Test Credentials:** `testuser` / `TestUser123!`

### Phase 4: Configure and Run Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `.env` with values from CDK outputs:

```
VITE_AWS_REGION=us-east-1
VITE_COGNITO_USER_POOL_ID=<CognitoUserPoolId>
VITE_COGNITO_USER_POOL_CLIENT_ID=<CognitoUserPoolClientId>
VITE_COGNITO_IDENTITY_POOL_ID=<CognitoIdentityPoolId>
VITE_AGENTCORE_RUNTIME_ARN=<AgentCoreRuntimeArn>
```

```bash
npm run dev
```

### Phase 5: Seed Demo Data (Optional)

If the Lambda seeder didn't run or you want to refresh data:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python data_seed.py --region us-east-1
```

## Testing the Application

1. Open http://localhost:5173
2. Log in with the test user credentials
3. Select a patient appointment from the list
4. Click "Start Call" and allow microphone access
5. Speak naturally — the agent will respond

**Demo Patients** (from seed data):
- John Smith (SSN last 4: 1234)
- Maria Garcia (SSN last 4: 5678)
- David Chen (SSN last 4: 9012)

## Clean Up

```bash
cd infrastructure
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
cdk destroy --force
```

Delete any remaining CloudWatch log groups:

```bash
aws logs describe-log-groups \
  --query 'logGroups[?contains(logGroupName, `NovaHealthcare`)].logGroupName' \
  --output text | xargs -I {} aws logs delete-log-group --log-group-name {}
```

## Troubleshooting

- **WebSocket connection fails** — verify Identity Pool config, check that the authenticated IAM role has `bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream`, and confirm AgentCore runtime is `ACTIVE`
- **No audio response** — ensure microphone access is granted in the browser and Nova Sonic 2 is enabled in Bedrock console
- **Authentication errors** — verify User Pool ID and Client ID match `.env` values, and confirm the user has a permanent password set
