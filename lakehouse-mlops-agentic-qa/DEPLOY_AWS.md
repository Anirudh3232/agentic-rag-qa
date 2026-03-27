# Deploy to AWS (ECR + App Runner)

Step-by-step guide to get the LMQ FastAPI server running on AWS App Runner from a locally-built Docker image. Estimated time: **15–20 minutes**.

## Prerequisites

- AWS CLI v2 configured with a profile that has admin access (`aws sts get-caller-identity` should return your account)
- Docker Desktop running locally
- The image builds and runs locally:

```bash
docker build -t lmq .
docker run --rm -p 8000:8000 lmq
# http://localhost:8000/health → {"status":"ok","version":"0.1.0"}
```

## 1. Set shell variables

```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO=lmq
IMAGE_TAG=latest
```

## 2. Create the ECR repository

```bash
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true
```

## 3. Authenticate Docker to ECR

```bash
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

## 4. Tag and push the image

```bash
docker tag lmq:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

docker push \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
```

## 5. Create the IAM role for App Runner → ECR access

App Runner needs permission to pull images from your private ECR repository.

```bash
# Create the trust policy
cat > /tmp/apprunner-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "build.apprunner.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role and attach the AWS-managed ECR access policy
aws iam create-role \
  --role-name lmq-apprunner-ecr-access \
  --assume-role-policy-document file:///tmp/apprunner-trust.json

aws iam attach-role-policy \
  --role-name lmq-apprunner-ecr-access \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

Save the role ARN — you will need it in the next step:

```bash
ACCESS_ROLE_ARN=$(aws iam get-role \
  --role-name lmq-apprunner-ecr-access \
  --query 'Role.Arn' --output text)
```

## 6. Create the App Runner service

```bash
aws apprunner create-service \
  --service-name lmq-api \
  --source-configuration "{
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"$ACCESS_ROLE_ARN\"
    },
    \"AutoDeploymentsEnabled\": false,
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\"
      }
    }
  }" \
  --instance-configuration "{
    \"Cpu\": \"0.25 vCPU\",
    \"Memory\": \"0.5 GB\"
  }" \
  --health-check-configuration "{
    \"Protocol\": \"HTTP\",
    \"Path\": \"/health\",
    \"Interval\": 20,
    \"Timeout\": 5,
    \"HealthyThreshold\": 1,
    \"UnhealthyThreshold\": 3
  }" \
  --region $AWS_REGION
```

This returns immediately. The service takes 2–5 minutes to provision.

## 7. Wait for the service to become active

```bash
aws apprunner list-services --region $AWS_REGION \
  --query 'ServiceSummaryList[?ServiceName==`lmq-api`].[Status,ServiceUrl]' \
  --output table
```

Re-run until `Status` shows `RUNNING`. Once active, copy the `ServiceUrl`.

## 8. Verify the deployment

```bash
SERVICE_URL=$(aws apprunner list-services --region $AWS_REGION \
  --query 'ServiceSummaryList[?ServiceName==`lmq-api`].ServiceUrl' \
  --output text)

# Health check
curl https://$SERVICE_URL/health

# Ask a question (stub mode — no API key needed)
curl -X POST https://$SERVICE_URL/v1/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What are quality gates in MLOps?", "top_k": 3}'
```

Expected health response:

```json
{"status": "ok", "version": "0.1.0"}
```

## 9. Deploy an update

After rebuilding the image locally:

```bash
docker build -t lmq .
docker tag lmq:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

SERVICE_ARN=$(aws apprunner list-services --region $AWS_REGION \
  --query 'ServiceSummaryList[?ServiceName==`lmq-api`].ServiceArn' \
  --output text)

aws apprunner start-deployment --service-arn $SERVICE_ARN --region $AWS_REGION
```

## 10. Tear down

```bash
# Delete the App Runner service
aws apprunner delete-service --service-arn $SERVICE_ARN --region $AWS_REGION

# Delete the ECR repository (and all images in it)
aws ecr delete-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION \
  --force

# Delete the IAM role
aws iam detach-role-policy \
  --role-name lmq-apprunner-ecr-access \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
aws iam delete-role --role-name lmq-apprunner-ecr-access
```

---

## What this deploys

```
┌──────────────┐      ┌──────────────┐      ┌──────────────────────┐
│ Docker image │─push─▶│  Amazon ECR  │─pull─▶│  AWS App Runner     │
│ (local)      │      │  lmq:latest  │      │  lmq-api             │
└──────────────┘      └──────────────┘      │  :8000               │
                                             │  GET  /health        │
                                             │  POST /v1/qa         │
                                             └──────────────────────┘
```

The container runs the same `lmq serve --host 0.0.0.0` command as it does locally. App Runner provides HTTPS, auto-scaling, and a public URL with no load balancer or VPC configuration.

## Broader architecture (not required for first deploy)

The repository includes infrastructure for the full MLOps platform. These are additive — none are required for the serving layer above.

| Service | Purpose | When to add |
|---------|---------|-------------|
| **Amazon S3** | Store raw documents, Parquet lake layers, and pipeline artifacts | When running the medallion pipeline in the cloud |
| **AWS Secrets Manager** | Inject `OPENAI_API_KEY` at runtime instead of env vars | When switching from stub mode to a live LLM |
| **AWS Glue Python Shell** | Run `lmq pipeline run` as a scheduled serverless job | When automating the data pipeline |
| **SageMaker MLflow** | Track pipeline runs, regression results, and promotion decisions | When you want persistent experiment history |

To provision all of these together, use the CloudFormation stack in `infra/cloudformation.yaml`:

```bash
aws cloudformation deploy \
  --stack-name lmq \
  --template-file infra/cloudformation.yaml \
  --capabilities CAPABILITY_NAMED_IAM
```

This creates the S3 bucket, Secrets Manager secret, ECR repository, IAM roles, and App Runner service in a single stack. The manual steps above are a subset of what this stack does, useful for understanding each piece individually.

## Cost estimate (minimal config)

| Resource | Config | Monthly cost |
|----------|--------|-------------|
| App Runner | 0.25 vCPU, 0.5 GB, paused when idle | ~$5 active / $0 paused |
| ECR | 1 image (~600 MB) | < $0.10 |
| **Total** | | **~$5/month** while testing |

App Runner pauses automatically when there is no traffic, so the cost for a portfolio project is near zero when idle.
