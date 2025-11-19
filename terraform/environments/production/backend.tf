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
# 4. Run: terraform init -migrate-state
# 5. Confirm migration when prompted

# terraform {
#   backend "s3" {
#     bucket                      = "health-platform-prod-terraform-state"
#     key                         = "production/terraform.tfstate"
#     region                      = "eu-amsterdam-1"
#     endpoint                    = "https://<namespace>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com"
#     skip_region_validation      = true
#     skip_credentials_validation = true
#     skip_metadata_api_check     = true
#     force_path_style            = true
#   }
# }
