# Terraform Backend Configuration for OCI Object Storage
#
# IMPORTANT: For first-time setup, comment out this entire file and use local state.
# After the OKE cluster is created, the object storage bucket will be available.
# Then uncomment this file and run `terraform init -migrate-state` to move state to OCI.
#
# Setup Instructions:
# 1. First run: Comment out this file, run terraform init/plan/apply
# 2. After apply: Note the terraform_state_bucket output
# 3. Uncomment this file and update the bucket name and endpoint
# 4. Configure OCI credentials (see below)
# 5. Run: terraform init -migrate-state
# 6. Confirm migration when prompted
#
# CREDENTIALS CONFIGURATION:
# The S3-compatible backend requires OCI Customer Secret Key credentials.
# These are NOT the same as OCI API keys used for the OCI provider.
#
# Setup OCI Customer Secret Key:
# 1. Oracle Cloud Console → User Settings → Customer Secret Keys
# 2. Generate a new Customer Secret Key
# 3. Note the Access Key and Secret Key (shown only once)
#
# Configure credentials (choose one method):
#
# Method 1 - Environment Variables (recommended):
#   export AWS_ACCESS_KEY_ID="<your-oci-access-key>"
#   export AWS_SECRET_ACCESS_KEY="<your-oci-secret-key>"
#
# Method 2 - AWS Credentials File:
#   Create ~/.aws/credentials with:
#   [default]
#   aws_access_key_id = <your-oci-access-key>
#   aws_secret_access_key = <your-oci-secret-key>
#
# SECURITY NOTE:
# skip_credentials_validation and skip_metadata_api_check are required for OCI
# compatibility (OCI Object Storage uses S3-compatible API). These settings bypass
# AWS-specific validation but do NOT bypass authentication. Proper OCI Customer
# Secret Key credentials are still required and validated by OCI.

# terraform {
#   backend "s3" {
#     bucket                      = "health-platform-prod-terraform-state"
#     key                         = "production/terraform.tfstate"
#     region                      = "eu-amsterdam-1"
#     endpoint                    = "https://<namespace>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com"
#     skip_region_validation      = true
#     skip_credentials_validation = true  # Required for OCI (not AWS)
#     skip_metadata_api_check     = true  # Required for OCI (not AWS)
#     force_path_style            = true
#   }
# }
