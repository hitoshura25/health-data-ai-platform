# Terraform Infrastructure - Oracle Kubernetes Engine (OKE)

This directory contains Terraform configuration for provisioning the Health Data AI Platform on Oracle Cloud Infrastructure's Always Free tier.

## Overview

- **Cloud Provider**: Oracle Cloud Infrastructure (OCI)
- **Target**: OKE (Oracle Kubernetes Engine) on Always Free tier
- **Cost**: $0/month (within free tier limits)
- **Region**: eu-amsterdam-1 (100% renewable energy)
- **Resources**: 3 ARM nodes (4 vCPU, 24 GB RAM total)

## Directory Structure

```
terraform/
├── modules/
│   └── kubernetes-cluster/
│       ├── interface.tf           # Cloud-agnostic interface
│       └── oracle-oke/            # Oracle OKE implementation
│           ├── main.tf            # OKE cluster configuration
│           ├── network.tf         # VCN, subnets, security lists
│           ├── storage.tf         # Object storage buckets
│           ├── outputs.tf         # Module outputs
│           ├── variables.tf       # Module variables
│           └── versions.tf        # Provider versions
├── environments/
│   └── production/
│       ├── main.tf                # Environment configuration
│       ├── variables.tf           # Environment variables
│       ├── outputs.tf             # Environment outputs
│       ├── backend.tf             # Remote state configuration
│       └── terraform.tfvars.example  # Template for secrets
└── README.md                      # This file
```

## Prerequisites

### 1. Oracle Cloud Account

1. Create an Oracle Cloud account at https://signup.cloud.oracle.com/
2. Navigate to your tenancy in the Oracle Cloud Console

### 2. OCI CLI Configuration

```bash
# Install OCI CLI (if not already installed)
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"

# Configure OCI CLI
oci setup config
```

### 3. Generate API Signing Key

```bash
# Create .oci directory
mkdir -p ~/.oci

# Generate API key pair
cd ~/.oci
openssl genrsa -out oci_api_key.pem 2048
chmod 600 oci_api_key.pem
openssl rsa -pubout -in oci_api_key.pem -out oci_api_key_public.pem

# Display public key (copy this)
cat oci_api_key_public.pem
```

### 4. Add API Key to Oracle Cloud

1. Log in to Oracle Cloud Console
2. Click on your profile → User Settings
3. Navigate to "API Keys" section
4. Click "Add API Key"
5. Paste the public key content
6. Note the fingerprint shown after adding

### 5. Gather Required Information

You'll need:
- **Tenancy OCID**: Profile → Tenancy → Tenancy Information → OCID
- **User OCID**: Profile → User Settings → User Information → OCID
- **Fingerprint**: Shown after adding API key
- **Compartment OCID**: Identity → Compartments (can use root compartment)
- **Region**: eu-amsterdam-1 (recommended for sustainability)

### 6. Install Terraform

```bash
# Install Terraform (v1.6.0 or later)
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify installation
terraform version
```

## Quick Start

### Step 1: Configure Variables

```bash
cd terraform/environments/production

# Copy the example tfvars file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your actual values
nano terraform.tfvars
```

Fill in your OCI credentials:
```hcl
tenancy_ocid     = "ocid1.tenancy.oc1..aaaaaaaa..."
user_ocid        = "ocid1.user.oc1..aaaaaaaa..."
fingerprint      = "aa:bb:cc:dd:ee:ff:..."
compartment_id   = "ocid1.compartment.oc1..aaaaaaaa..."
```

### Step 2: Initialize Terraform

```bash
# Initialize Terraform (downloads providers)
terraform init

# Validate configuration
terraform validate

# Format code
terraform fmt -recursive
```

### Step 3: Plan Deployment

```bash
# Review planned changes
terraform plan

# Save plan to file (optional)
terraform plan -out=tfplan
```

### Step 4: Apply Configuration

```bash
# Apply changes (creates infrastructure)
terraform apply

# Or apply saved plan
terraform apply tfplan

# Type 'yes' when prompted to confirm
```

**Expected provisioning time**: 10-15 minutes

### Step 5: Configure kubectl

```bash
# Save kubeconfig
terraform output -raw kubeconfig > ~/.kube/config-oke
chmod 600 ~/.kube/config-oke

# Set KUBECONFIG environment variable
export KUBECONFIG=~/.kube/config-oke

# Verify cluster access
kubectl cluster-info
kubectl get nodes

# Expected output (version depends on your kubernetes_version variable):
# NAME                              STATUS   ROLES   AGE   VERSION
# oke-system-pool-xxxxx             Ready    node    5m    v1.28.x
# oke-app-pool-xxxxx-0              Ready    node    5m    v1.28.x
# oke-app-pool-xxxxx-1              Ready    node    5m    v1.28.x
```

### Step 6: View Resource Summary

```bash
# Display provisioned resources
terraform output resource_summary
```

## Configuration Options

### Node Pool Configuration

Default configuration (3 nodes, 4 vCPU, 24 GB RAM):

```hcl
node_pools = [
  {
    name       = "system-pool"
    ocpu_count = 2
    memory_gb  = 12
    node_count = 1
    auto_scale = false
    min_nodes  = 1
    max_nodes  = 1
  },
  {
    name       = "app-pool"
    ocpu_count = 1
    memory_gb  = 6
    node_count = 2
    auto_scale = false
    min_nodes  = 2
    max_nodes  = 2
  }
]
```

### Network Configuration

Default network ranges:

```hcl
vcn_cidr     = "10.0.0.0/16"      # VCN CIDR
pod_cidr     = "10.244.0.0/16"    # Pod network
service_cidr = "10.96.0.0/16"     # Service network
```

Subnets:
- API Subnet: 10.0.1.0/24 (public)
- Node Subnet: 10.0.2.0/24 (private/public based on config)
- Load Balancer Subnet: 10.0.3.0/24 (public)

### Cluster Type

```hcl
cluster_type = "BASIC_CLUSTER"  # FREE control plane
# or
cluster_type = "ENHANCED_CLUSTER"  # $0.10/hour (paid)
```

## Remote State Configuration

After initial setup, migrate state to OCI Object Storage:

### Step 1: Get Object Storage Namespace

```bash
terraform output object_storage_namespace
# Example output: frxxxxxxxx
```

### Step 2: Update backend.tf

Edit `terraform/environments/production/backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket                      = "health-platform-prod-terraform-state"
    key                         = "production/terraform.tfstate"
    region                      = "eu-amsterdam-1"
    endpoint                    = "https://<YOUR_NAMESPACE>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    force_path_style            = true
  }
}
```

Replace `<YOUR_NAMESPACE>` with the actual namespace.

### Step 3: Migrate State

```bash
# Reinitialize with new backend
terraform init -migrate-state

# Confirm migration when prompted
```

## Useful Commands

### View Outputs

```bash
# List all outputs
terraform output

# Get specific output
terraform output cluster_id
terraform output cluster_endpoint

# Get kubeconfig
terraform output -raw kubeconfig > ~/.kube/config-oke
```

### Update Infrastructure

```bash
# Pull latest state
terraform refresh

# Plan changes
terraform plan

# Apply changes
terraform apply
```

### Destroy Infrastructure

```bash
# CAREFUL: This deletes all resources
terraform plan -destroy
terraform destroy

# Type 'yes' to confirm
```

### State Management

```bash
# List resources in state
terraform state list

# Show resource details
terraform state show module.kubernetes_cluster.oci_containerengine_cluster.k8s_cluster

# Remove resource from state (advanced)
terraform state rm module.kubernetes_cluster.oci_core_vcn.k8s_vcn
```

## Troubleshooting

### Issue: "Service limit exceeded"

**Solution**: Request service limit increase

1. Oracle Console → Governance → Limits, Quotas and Usage
2. Request increase for:
   - Compute: ARM CPU cores (need 4)
   - Block Volumes: 200 GB

### Issue: "Insufficient capacity"

**Solution**: Try different availability domain

Modify `main.tf` in the oracle-oke module:

```hcl
placement_configs {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[1].name  # Try AD 2
  subnet_id          = oci_core_subnet.k8s_node_subnet.id
}
```

### Issue: "Cannot connect to cluster"

**Solutions**:

1. Verify kubeconfig:
   ```bash
   terraform output -raw kubeconfig
   ```

2. Check OCI CLI configuration:
   ```bash
   oci iam region list
   ```

3. Regenerate kubeconfig via OCI CLI:
   ```bash
   oci ce cluster create-kubeconfig \
     --cluster-id $(terraform output -raw cluster_id) \
     --file ~/.kube/config-oke \
     --region eu-amsterdam-1
   ```

### Issue: "Authentication failed"

**Solutions**:

1. Verify API key fingerprint matches:
   ```bash
   openssl rsa -pubout -outform DER -in ~/.oci/oci_api_key.pem | openssl md5 -c
   ```

2. Check private key permissions:
   ```bash
   chmod 600 ~/.oci/oci_api_key.pem
   ```

3. Verify OCI credentials in terraform.tfvars

## Cost Monitoring

### Free Tier Limits

Always Free resources:
- Compute: 4 ARM Ampere A1 cores
- Memory: 24 GB RAM
- Block Storage: 200 GB total
- Object Storage: 20 GB total
- Load Balancer: 1 flexible load balancer (10 Mbps)
- Outbound Data Transfer: 10 TB/month

### Check Resource Usage

```bash
# Check node resources
kubectl describe nodes

# Monitor storage usage
kubectl get pvc -A

# View object storage usage (OCI Console)
# Storage → Object Storage → Buckets
```

## Next Steps

After successfully provisioning the OKE cluster:

1. **Module 2**: Deploy infrastructure Helm charts (PostgreSQL, Redis, MinIO, RabbitMQ)
2. **Module 3**: Deploy WebAuthn stack Helm chart
3. **Module 4**: Deploy health services Helm charts
4. **Module 5**: Set up observability stack (Prometheus, Grafana, Jaeger, Loki)
5. **Module 6**: Configure security (RBAC, NetworkPolicies, Sealed Secrets)
6. **Module 7**: Set up GitOps with ArgoCD
7. **Module 8**: Configure disaster recovery with Velero

## References

- [Oracle Cloud Always Free](https://www.oracle.com/cloud/free/)
- [OKE Documentation](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
- [Terraform OCI Provider](https://registry.terraform.io/providers/oracle/oci/latest/docs)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review OCI documentation
3. Check Terraform provider documentation
4. Open an issue in the project repository

## License

This configuration is part of the Health Data AI Platform project.
