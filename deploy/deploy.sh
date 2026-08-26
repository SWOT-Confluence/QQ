#!/usr/bin/env bash
# deploy/deploy.sh
# ================
# Build, push, and deploy the QQ FLPE algorithm container.
#
# Usage:
#   bash deploy/deploy.sh <registry> <repository> <prefix> <s3_state_bucket> <profile>
#
# Arguments:
#   registry        AWS ECR registry URI, e.g. 123456789012.dkr.ecr.us-west-2.amazonaws.com
#   repository      ECR repository name, e.g. swot-confluence-qq
#   prefix          Resource name prefix for Terraform, e.g. confluence-dev
#   s3_state_bucket S3 bucket name for Terraform remote state
#   profile         AWS CLI profile name
#
# This script follows the identical 5-argument convention used by all other
# SWOT-Confluence FLPE algorithm deploy scripts (momma, hivdi, sad, moi, etc.).

set -euo pipefail

REGISTRY=$1
REPOSITORY=$2
PREFIX=$3
S3_BUCKET=$4
PROFILE=$5

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== QQ FLPE deploy ==="
echo "  REGISTRY   : ${REGISTRY}"
echo "  REPOSITORY : ${REPOSITORY}"
echo "  PREFIX     : ${PREFIX}"
echo "  S3_BUCKET  : ${S3_BUCKET}"
echo "  PROFILE    : ${PROFILE}"
echo ""


GIT_COMMIT="$(
  git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || echo unknown
)"

GIT_DESCRIBE="$(
  git -C "${REPO_ROOT}" describe --tags --always --dirty 2>/dev/null || echo unknown
)"


# -----------------------------------------------------------------------
# 1. Build Docker image
# -----------------------------------------------------------------------
echo "[1/4] Building Docker image..."
# docker build -t "${REGISTRY}/${REPOSITORY}:latest" "${REPO_ROOT}"

docker build \
  --build-arg GIT_COMMIT="${GIT_COMMIT}" \
  --build-arg GIT_DESCRIBE="${GIT_DESCRIBE}" \
  -t "${REGISTRY}/${REPOSITORY}:latest" \
  "${REPO_ROOT}"

# -----------------------------------------------------------------------
# 2. Authenticate to ECR and push
# -----------------------------------------------------------------------
echo "[2/4] Authenticating to ECR..."
aws ecr get-login-password --profile "${PROFILE}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

echo "[3/4] Pushing image to ECR..."
docker push "${REGISTRY}/${REPOSITORY}:latest"

# -----------------------------------------------------------------------
# 3. Apply Terraform
# -----------------------------------------------------------------------
echo "[4/4] Applying Terraform..."
cd "${REPO_ROOT}/terraform"

terraform init \
  -backend-config="bucket=${S3_BUCKET}" \
  -backend-config="key=${PREFIX}/qq/terraform.tfstate" \
  -backend-config="region=us-west-2" \
  -reconfigure

terraform apply \
  -var="prefix=${PREFIX}" \
  -var="registry=${REGISTRY}" \
  -var="repository=${REPOSITORY}" \
  -var="profile=${PROFILE}" \
  -auto-approve

echo ""
echo "=== QQ FLPE deploy complete ==="
