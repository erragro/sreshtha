# Sreshtha — Production Deployment Guide

This document describes the manual production deployment process for Sreshtha on Google Cloud Platform.

The production deployment is intentionally **manual**. GitHub is the source repository, while Docker images are built locally, pushed to Artifact Registry, and deployed manually to Cloud Run.

## Deployment Ownership

The GCP production environment is already configured and is managed separately from normal application development.

The designated deployment owner is responsible for:

- GCP authentication
- Artifact Registry
- Docker image builds and pushes
- Cloud Run deployments
- Cloud SQL connectivity
- Secret Manager configuration
- Production smoke testing
- Cloud Run logs and troubleshooting
- Production rollback

Application developers do not need GCP access for normal code development.

Do not modify production infrastructure unless explicitly required.

---

## 1. Production Architecture

```text
GitHub
  │
  │ source code
  ▼
Developer Mac
  │
  │ docker build
  ▼
Google Artifact Registry
  │
  ├── sreshtha/api:<tag>
  └── sreshtha/web:<tag>
        │
        ▼
   Google Cloud Run
        │
        ├── sreshtha-web
        │       │
        │       └── nginx
        │              │
        │              ▼
        │        sreshtha-api
        │
        └── sreshtha-api
                │
                ├── Cloud SQL PostgreSQL
                ├── Secret Manager
                ├── Cloud Storage
                └── Vertex AI / external APIs
```

### Production components

| Component | Resource |
|---|---|
| GCP Project | `gen-lang-client-0368265372` |
| Region | `asia-south1` |
| Artifact Registry | `sreshtha` |
| API Cloud Run service | `sreshtha-api` |
| Frontend Cloud Run service | `sreshtha-web` |
| Cloud SQL instance | `sreshtha-db` |
| PostgreSQL database | `sreshtha` |
| Runtime service account | `sreshtha-run` |
| Contracts bucket | `gen-lang-client-0368265372-sreshtha-contracts` |

---

# 2. Deployment Philosophy

Production deployment follows this process:

```text
GitHub main
    ↓
Make code/config changes
    ↓
Test locally
    ↓
Commit + push
    ↓
Pull latest main on deployment machine
    ↓
Build Docker image
    ↓
Push image to Artifact Registry
    ↓
Deploy image to Cloud Run
    ↓
Run production smoke tests
```

### Production Source of Truth

`origin/main` is the source of truth for production application code.

Before any production deployment:

```bash
git checkout main
git pull origin main
```

Verify the commit being deployed:

```bash
git rev-parse --short HEAD
```

The Docker image tag should correspond to this Git commit.

There is currently **no automatic GitHub → Cloud Run CI/CD deployment**.

Do not re-enable or depend on the previous Cloud Build trigger unless the deployment architecture is deliberately changed.

---

# 3. Prerequisites

Install and authenticate:

- Git
- Docker
- Google Cloud CLI (`gcloud`)

Authenticate:

```bash
gcloud auth login
```

Set the production project:

```bash
gcloud config set project gen-lang-client-0368265372
```

Verify:

```bash
gcloud config get-value project
```

Expected:

```text
gen-lang-client-0368265372
```

Authenticate Docker with Artifact Registry:

```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

---

# 5. Production Configuration — Do Not Change Accidentally

The following configuration is part of the established production architecture.

Do not change these values or configurations unless the production architecture is
deliberately being modified and the deployment process is reviewed accordingly.

| Configuration | Current value |
|---|---|
| GCP Project | `gen-lang-client-0368265372` |
| Region | `asia-south1` |
| Artifact Registry | `sreshtha` |
| API Cloud Run service | `sreshtha-api` |
| Frontend Cloud Run service | `sreshtha-web` |
| Cloud SQL instance | `sreshtha-db` |
| PostgreSQL database | `sreshtha` |
| Runtime service account | `sreshtha-run` |
| Contracts bucket | `gen-lang-client-0368265372-sreshtha-contracts` |

In particular, do not casually change:

- Cloud Run service names
- Cloud SQL configuration
- Runtime service account
- Secret Manager secret names
- Artifact Registry repository
- Production API URL
- Production frontend URL
- `API_UPSTREAM`
- Frontend nginx proxy configuration
- The root API `Dockerfile`
- Alembic migration configuration

Do not introduce GitHub Actions, Cloud Build deployment triggers, or another
automatic deployment mechanism unless the production deployment architecture is
deliberately changed.

The current production deployment process is manual.

---

# 6. Deployment Variables

From the repository root, define:

```bash
export PROJECT_ID="gen-lang-client-0368265372"
export REGION="asia-south1"

export API_SERVICE="sreshtha-api"
export WEB_SERVICE="sreshtha-web"

export ARTIFACT_REPO="sreshtha"

export RUNTIME_SA="sreshtha-run@${PROJECT_ID}.iam.gserviceaccount.com"

export CLOUD_SQL_CONNECTION="gen-lang-client-0368265372:asia-south1:sreshtha-db"

export API_URL="https://sreshtha-api-651858445044.asia-south1.run.app"
export WEB_URL="https://sreshtha-web-651858445044.asia-south1.run.app"
```

Verify:

```bash
echo "$PROJECT_ID"
echo "$REGION"
echo "$API_SERVICE"
echo "$WEB_SERVICE"
echo "$CLOUD_SQL_CONNECTION"
```

---

# 6. Verify GCP Resources Before Deployment

Do not recreate resources blindly.

## Artifact Registry

Verify:

```bash
gcloud artifacts repositories describe sreshtha \
  --location=asia-south1
```

The repository should already exist.

List images:

```bash
gcloud artifacts docker images list \
  asia-south1-docker.pkg.dev/gen-lang-client-0368265372/sreshtha
```

---

## Cloud SQL

Verify:

```bash
gcloud sql instances describe sreshtha-db
```

The instance should show:

```text
state: RUNNABLE
databaseVersion: POSTGRES_16
region: asia-south1
```

Verify the database:

```bash
gcloud sql databases list \
  --instance=sreshtha-db
```

The `sreshtha` database should exist.

---

## Cloud Run

Verify the API:

```bash
gcloud run services describe sreshtha-api \
  --region=asia-south1
```

Verify the frontend:

```bash
gcloud run services describe sreshtha-web \
  --region=asia-south1
```

---

# 7. Secrets

Production secrets are stored in Google Secret Manager.

Current secrets:

```text
database-url
jwt-secret
openai-api-key
sarvam-api-key
```

Verify:

```bash
gcloud secrets list
```

Do **not** print secret values in the terminal or put passwords/API keys directly into deployment commands.

Cloud Run receives these secrets as environment variables.

Current mapping:

```text
DATABASE_URL    → database-url:latest
JWT_SECRET      → jwt-secret:latest
OPENAI_API_KEY  → openai-api-key:latest
SARVAM_API_KEY  → sarvam-api-key:latest
```

---

# 8. API Docker Image

## Important

The production API image must be built using the **root `Dockerfile`**:

```text
./Dockerfile
```

Do not use:

```text
./Dockerfile.cloudrun
```

for the current production deployment.

The root Dockerfile includes the Alembic migration directory:

```text
/app/alembic
```

This is required because the production container runs database migrations during startup.

### Do not remove Alembic from the production image

The production container runs database migrations during startup.

The image must contain:

```text
/app/alembic
/app/alembic.ini
```

Any Dockerfile change that removes these files can cause the application to start
without a usable database schema and result in authentication/API failures.

---

# 9. Build the API

First check the current commit:

```bash
git rev-parse --short HEAD
```

Use the commit SHA as the image tag:

```bash
export TAG=$(git rev-parse --short HEAD)
echo "$TAG"
```

Build:

```bash
docker build \
  --platform linux/amd64 \
  -t asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api:${TAG} \
  -f Dockerfile .
```

The `linux/amd64` platform is intentional because Cloud Run uses the amd64 architecture for this deployment.

---

# 10. Push the API Image

```bash
docker push \
  asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api:${TAG}
```

Verify:

```bash
gcloud artifacts docker images list \
  asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api
```

---

# 11. Deploy the API to Cloud Run

Deploy:

```bash
gcloud run deploy ${API_SERVICE} \
  --image asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api:${TAG} \
  --region ${REGION} \
  --platform managed \
  --service-account ${RUNTIME_SA} \
  --port 8000 \
  --add-cloudsql-instances ${CLOUD_SQL_CONNECTION} \
  --set-secrets "DATABASE_URL=database-url:latest,JWT_SECRET=jwt-secret:latest,OPENAI_API_KEY=openai-api-key:latest,SARVAM_API_KEY=sarvam-api-key:latest" \
  --allow-unauthenticated
```

### Important

Do not replace the secret configuration with a literal:

```text
DATABASE_URL=...
```

The production database URL must remain managed through Secret Manager.

---

# 12. Database Migrations

The API container runs Alembic migrations during startup.

After deployment, inspect logs:

```bash
gcloud run services logs read ${API_SERVICE} \
  --region=${REGION} \
  --limit=100
```

A successful deployment should show migrations completing and the application starting.

For example:

```text
Running upgrade -> 001
...
Running upgrade 015 -> 016
bootstrap complete
Application startup complete.
```

The exact migration number may increase as the application evolves.

Do not manually create application tables in production unless specifically required by a migration/recovery procedure.

---

# 13. API Smoke Tests

Check the health endpoint:

```bash
curl -i "${API_URL}/ping"
```

Expected:

```text
HTTP/2 200
```

Then test authentication using an existing designated production test account.

Do not create test users in production as part of the normal deployment process.

### Login

```bash
curl -i -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "PRODUCTION_TEST_EMAIL",
    "password": "PRODUCTION_TEST_PASSWORD"
  }'
```

A successful login should return a JWT.

The production test account credentials must not be committed to the repository
or documented in this file.

Use the returned token to test:

```text
GET /auth/me
```

Also verify:

```text
GET /api/modules
```

---

# 14. Frontend Docker Image

The frontend is served through nginx.

The production nginx configuration uses:

```text
API_UPSTREAM
```

as a runtime environment variable.

The Docker image uses nginx's environment-template mechanism.

The Dockerfile therefore copies the nginx configuration into:

```text
/etc/nginx/templates/default.conf.template
```

rather than directly into:

```text
/etc/nginx/conf.d/default.conf
```

This allows Cloud Run to provide the API URL at runtime.

---

# 15. Frontend API Configuration

Production:

```text
API_UPSTREAM=https://sreshtha-api-651858445044.asia-south1.run.app
```

The frontend nginx proxy forwards API requests to this upstream.

The proxy configuration must use:

```nginx
proxy_set_header Host $proxy_host;
```

rather than:

```nginx
proxy_set_header Host $host;
```

This is important for Cloud Run because using `$host` can cause the frontend service to proxy requests back to itself, resulting in recursive proxying and errors such as:

```text
Request Header Or Cookie Too Large
```

---

# 16. Build the Frontend

Use the same commit tag:

```bash
export TAG=$(git rev-parse --short HEAD)
```

Build:

```bash
docker build \
  --platform linux/amd64 \
  -t asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web:${TAG} \
  -f frontend/Dockerfile \
  frontend
```

---

# 17. Push the Frontend Image

```bash
docker push \
  asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web:${TAG}
```

Verify:

```bash
gcloud artifacts docker images list \
  asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web
```

---

# 18. Deploy the Frontend to Cloud Run

```bash
gcloud run deploy ${WEB_SERVICE} \
  --image asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web:${TAG} \
  --region ${REGION} \
  --platform managed \
  --service-account ${RUNTIME_SA} \
  --port 80 \
  --set-env-vars "API_UPSTREAM=${API_URL}" \
  --allow-unauthenticated
```

---

# 19. Frontend Smoke Tests

Check the frontend health endpoint:

```bash
curl -i "${WEB_URL}/ping"
```

Expected:

```text
HTTP/2 200
```

Expected response:

```json
{"status":"ok"}
```

Check the frontend itself:

```bash
curl -I "${WEB_URL}"
```

Expected:

```text
HTTP/2 200
```

Expected content type:

```text
text/html
```

---

# 20. Browser Verification

After both services deploy:

1. Open the production frontend.
2. Log in.
3. Confirm `/auth/me` succeeds.
4. Confirm application data loads.
5. Open the user menu.
6. Click **Sign out**.
7. Confirm the session is cleared.
8. Confirm the application redirects to `/login`.
9. Log in again.
10. Confirm the authenticated application works normally.

---

# 21. Cloud Run Revisions

Every deployment creates a new Cloud Run revision.

Check revisions:

```bash
gcloud run revisions list \
  --service=${API_SERVICE} \
  --region=${REGION}
```

Frontend:

```bash
gcloud run revisions list \
  --service=${WEB_SERVICE} \
  --region=${REGION}
```

Check current traffic:

```bash
gcloud run services describe ${API_SERVICE} \
  --region=${REGION} \
  --format="yaml(status.traffic)"
```

And:

```bash
gcloud run services describe ${WEB_SERVICE} \
  --region=${REGION} \
  --format="yaml(status.traffic)"
```

The latest successful deployment should normally receive 100% traffic.

---

# 22. Logs

API:

```bash
gcloud run services logs read sreshtha-api \
  --region=asia-south1 \
  --limit=100
```

Frontend:

```bash
gcloud run services logs read sreshtha-web \
  --region=asia-south1 \
  --limit=100
```

For live logs:

```bash
gcloud beta run services logs tail sreshtha-api \
  --region=asia-south1
```

or:

```bash
gcloud beta run services logs tail sreshtha-web \
  --region=asia-south1
```

---

# 23. Rollback

If the latest revision is broken, first list revisions:

```bash
gcloud run revisions list \
  --service=sreshtha-api \
  --region=asia-south1
```

Identify the last known-good revision.

Then move traffic back:

```bash
gcloud run services update-traffic sreshtha-api \
  --region=asia-south1 \
  --to-revisions=KNOWN_GOOD_REVISION=100
```

For frontend:

```bash
gcloud run services update-traffic sreshtha-web \
  --region=asia-south1 \
  --to-revisions=KNOWN_GOOD_REVISION=100
```

Replace `KNOWN_GOOD_REVISION` with the actual revision name.

---

# 24. Normal Production Update Procedure

For a normal application update, keep application development and production
deployment as separate responsibilities.

## Application developer

Before starting work:

```bash
git checkout main
git pull origin main
```

Make the required changes and test locally.

For example:

```bash
docker compose up --build
```

Run the relevant application tests and manually verify the affected functionality.

Review the changes:

```bash
git status
git diff
```

Commit and push the changes:

```bash
git add .
git commit -m "Describe the change"
git push origin main
```

For larger changes, preferably use a feature branch and merge into `main`.

## Deployment owner

After the application change has been pushed:

```bash
git checkout main
git pull origin main
```

Verify the commit:

```bash
git rev-parse --short HEAD
```

Only then build the Docker image.

The deployment owner must deploy the commit currently present on
`origin/main`, rather than an older local checkout or an unrelated branch.

### Build images

Use:

```bash
TAG=$(git rev-parse --short HEAD)
```

Build and push the API and/or frontend image.

### Deploy to Cloud Run

Deploy only the service that changed.

### Smoke test

Verify:

```text
API /ping
Frontend /ping
Authentication
Affected functionality
Logs
```

---

# 25. Deploying Only One Service

If only the backend changes:

```text
Build API
  ↓
Push API
  ↓
Deploy API
  ↓
Test API
```

There is no need to rebuild the frontend.

If only the frontend changes:

```text
Build web
  ↓
Push web
  ↓
Deploy web
  ↓
Test frontend
```

There is no need to rebuild the API.

---

# 26. Image Tagging

The preferred tag is the Git commit SHA:

```bash
TAG=$(git rev-parse --short HEAD)
```

For example:

```text
<git-commit-sha>
```

This makes it possible to identify exactly which source revision produced a production image.

Avoid relying exclusively on mutable tags such as:

```text
latest
```

Commit-based tags provide a clear deployment history.

---

# 27. Current Production URLs

API:

```text
https://sreshtha-api-651858445044.asia-south1.run.app
```

Frontend:

```text
https://sreshtha-web-651858445044.asia-south1.run.app
```

These URLs may change if the architecture is changed.

---

# 28. Current Production Service Account

Cloud Run runtime service account:

```text
sreshtha-run@gen-lang-client-0368265372.iam.gserviceaccount.com
```

The service account is used by the Cloud Run API and frontend services.

It provides the runtime access required for:

- Cloud SQL
- Secret Manager
- Artifact Registry
- Cloud Storage
- Vertex AI
- Cloud Run-related runtime operations
- Cloud Logging

Do not replace this account with a personal user account.

---

# 29. Important Security Rules

Never commit:

```text
.env
database passwords
JWT secrets
OpenAI API keys
Sarvam API keys
service account private keys
```

Never put production credentials directly into:

```text
docker build
docker push
gcloud run deploy
```

Use Secret Manager for production secrets.

---

# 30. Troubleshooting

## API returns 500 and database tables do not exist

Check Cloud Run logs:

```bash
gcloud run services logs read sreshtha-api \
  --region=asia-south1 \
  --limit=100
```

Look for Alembic errors.

If you see:

```text
Path doesn't exist: /app/alembic
```

the wrong Dockerfile/image was used.

Use the root:

```text
Dockerfile
```

not:

```text
Dockerfile.cloudrun
```

---

## API starts but migrations fail

Verify the container contains:

```text
/app/alembic
/app/alembic.ini
```

Local verification:

```bash
docker run --rm IMAGE_NAME \
  sh -c 'ls -la /app/alembic && ls -la /app/alembic/versions'
```

---

## Frontend `/ping` returns 502

Check frontend logs:

```bash
gcloud run services logs read sreshtha-web \
  --region=asia-south1 \
  --limit=100
```

Verify:

```text
API_UPSTREAM
```

Check that it points to the API service, not the frontend service.

Correct:

```text
https://sreshtha-api-651858445044.asia-south1.run.app
```

---

## Frontend gets recursive proxy errors

If nginx reports errors such as:

```text
Request Header Or Cookie Too Large
```

check:

```nginx
proxy_set_header Host $proxy_host;
```

Do not change this back to:

```nginx
proxy_set_header Host $host;
```

The latter can cause Cloud Run requests to loop back to the frontend service.

---

# 31. Production Deployment Checklist

Before deployment:

```text
[ ] git status is clean or expected changes are committed
[ ] correct main branch
[ ] latest main pulled
[ ] working tree contains only expected changes
[ ] no local commits exist that are not on origin/main
[ ] deployment commit verified with git rev-parse --short HEAD
[ ] local tests pass
[ ] Docker build succeeds
[ ] image tag matches Git commit
[ ] Artifact Registry authentication works
```

API deployment:

```text
[ ] API image built with root Dockerfile
[ ] /app/alembic exists in image
[ ] API image pushed
[ ] Cloud Run deployment succeeds
[ ] migrations complete
[ ] /ping returns 200
[ ] /auth/login works
[ ] /auth/me works
[ ] /api/modules works
```

Frontend deployment:

```text
[ ] frontend image built
[ ] frontend image pushed
[ ] API_UPSTREAM points to API Cloud Run service
[ ] Cloud Run deployment succeeds
[ ] /ping returns 200
[ ] / returns 200
[ ] login works
[ ] application data loads
[ ] logout works
```

After deployment:

```text
[ ] Cloud Run revision receives expected traffic
[ ] no unexpected errors in logs
[ ] production application manually verified
```

Never force-push `main` as part of the normal development or deployment process.

---

# 32. What This Deployment Does Not Use

The current production process does **not** depend on:

- GitHub Actions
- Cloud Build triggers
- Automatic GitHub → Cloud Run deployment
- Personal GitHub OAuth credentials at deployment time

Cloud Build / GitHub integration may exist in the GCP project from previous experimentation, but it is not part of the current production deployment workflow.

The authoritative production path is:

```text
GitHub main
    ↓
Local Docker build
    ↓
Artifact Registry
    ↓
Cloud Run
```

---

# 33. Final Reference

Before using the commands below, make sure the repository is on the intended
production commit:

```bash
git checkout main
git pull origin main
git rev-parse --short HEAD
```

Use that commit SHA as `TAG`.

## API

```bash
docker build \
  --platform linux/amd64 \
  -t asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api:${TAG} \
  -f Dockerfile .

docker push \
  asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api:${TAG}

gcloud run deploy ${API_SERVICE} \
  --image asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/api:${TAG} \
  --region ${REGION} \
  --platform managed \
  --service-account ${RUNTIME_SA} \
  --port 8000 \
  --add-cloudsql-instances ${CLOUD_SQL_CONNECTION} \
  --set-secrets "DATABASE_URL=database-url:latest,JWT_SECRET=jwt-secret:latest,OPENAI_API_KEY=openai-api-key:latest,SARVAM_API_KEY=sarvam-api-key:latest" \
  --allow-unauthenticated
```

## Frontend

```bash
docker build \
  --platform linux/amd64 \
  -t asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web:${TAG} \
  -f frontend/Dockerfile \
  frontend

docker push \
  asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web:${TAG}

gcloud run deploy ${WEB_SERVICE} \
  --image asia-south1-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/web:${TAG} \
  --region ${REGION} \
  --platform managed \
  --service-account ${RUNTIME_SA} \
  --port 80 \
  --set-env-vars "API_UPSTREAM=${API_URL}" \
  --allow-unauthenticated
```

---

**End of document.**
