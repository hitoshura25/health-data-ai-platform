# Module 1: Terraform Infrastructure
## Oracle Cloud Infrastructure - OKE Cluster Provisioning

**Estimated Time:** 1 week
**Dependencies:** None (can start immediately)
**Deliverables:** Working OKE cluster accessible via kubectl

---

## Objectives

1. Provision Oracle Kubernetes Engine (OKE) cluster using Terraform
2. Configure Virtual Cloud Network (VCN) and networking
3. Set up block storage and object storage
4. Configure load balancer
5. Implement cloud-agnostic Terraform module pattern

---

## Directory Structure

```
terraform/
├── modules/
│   └── kubernetes-cluster/
│       ├── interface.tf           # Cloud-agnostic interface
│       ├── oracle-oke/            # Oracle implementation
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   ├── outputs.tf
│       │   ├── network.tf
│       │   ├── storage.tf
│       │   └── versions.tf
│       ├── gcp-gke/               # Future: GCP implementation
│       └── aws-eks/               # Future: AWS implementation
├── environments/
│   ├── production/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── development/
│       ├── main.tf
│       └── terraform.tfvars
└── README.md
```

---

## Implementation Steps

### Step 1: Set Up Oracle Cloud Account

```bash
# 1. Create Oracle Cloud account (if not exists)
# Visit: https://signup.cloud.oracle.com/

# 2. Create API signing key for Terraform
mkdir -p ~/.oci
cd ~/.oci
openssl genrsa -out oci_api_key.pem 2048
chmod 600 oci_api_key.pem
openssl rsa -pubout -in oci_api_key.pem -out oci_api_key_public.pem

# 3. Add public key to Oracle Cloud Console
# Navigate to: User Settings → API Keys → Add API Key

# 4. Get required information:
#    - Tenancy OCID
#    - User OCID
#    - Region identifier
#    - Fingerprint (shown after adding API key)

# 5. Create OCI config file
cat > ~/.oci/config <<EOF
[DEFAULT]
user=<USER_OCID>
fingerprint=<API_KEY_FINGERPRINT>
tenancy=<TENANCY_OCID>
region=eu-amsterdam-1
key_file=~/.oci/oci_api_key.pem
EOF
```

### Step 2: Create Cloud-Agnostic Interface

```hcl
# terraform/modules/kubernetes-cluster/interface.tf
# Defines standard interface for all cloud providers

variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = string
}

variable "region" {
  description = "Cloud region for cluster deployment"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "v1.28.2"
}

variable "node_pools" {
  description = "Node pool configurations"
  type = list(object({
    name         = string
    ocpu_count   = number
    memory_gb    = number
    node_count   = number
    auto_scale   = bool
    min_nodes    = number
    max_nodes    = number
  }))
}

variable "pod_cidr" {
  description = "CIDR for pod network"
  type        = string
  default     = "10.244.0.0/16"
}

variable "service_cidr" {
  description = "CIDR for service network"
  type        = string
  default     = "10.96.0.0/16"
}

# Standard outputs (implemented by each cloud provider)
output "cluster_id" {
  description = "Cluster identifier"
  value       = ""  # Implemented by provider module
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = ""
}

output "kubeconfig" {
  description = "Kubeconfig for cluster access"
  value       = ""
  sensitive   = true
}

output "node_pool_ids" {
  description = "IDs of created node pools"
  value       = []
}
```

### Step 3: Create Oracle OKE Module

**File: `terraform/modules/kubernetes-cluster/oracle-oke/versions.tf`**

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.25"
    }
  }
}
```

**File: `terraform/modules/kubernetes-cluster/oracle-oke/variables.tf`**

```hcl
variable "compartment_id" {
  description = "OCI Compartment OCID"
  type        = string
}

variable "cluster_name" {
  description = "Name of the OKE cluster"
  type        = string
}

variable "region" {
  description = "OCI region"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "v1.28.2"
}

variable "vcn_cidr" {
  description = "CIDR block for VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "pod_cidr" {
  description = "CIDR for pod network"
  type        = string
  default     = "10.244.0.0/16"
}

variable "service_cidr" {
  description = "CIDR for service network"
  type        = string
  default     = "10.96.0.0/16"
}

variable "node_pools" {
  description = "Node pool configurations"
  type = list(object({
    name         = string
    ocpu_count   = number
    memory_gb    = number
    node_count   = number
    auto_scale   = bool
    min_nodes    = number
    max_nodes    = number
  }))
  default = [
    {
      name         = "system-pool"
      ocpu_count   = 2
      memory_gb    = 12
      node_count   = 1
      auto_scale   = false
      min_nodes    = 1
      max_nodes    = 1
    },
    {
      name         = "app-pool"
      ocpu_count   = 1
      memory_gb    = 6
      node_count   = 2
      auto_scale   = false
      min_nodes    = 2
      max_nodes    = 2
    }
  ]
}

variable "cluster_type" {
  description = "OKE cluster type: BASIC_CLUSTER (free) or ENHANCED_CLUSTER ($0.10/hr)"
  type        = string
  default     = "BASIC_CLUSTER"

  validation {
    condition     = contains(["BASIC_CLUSTER", "ENHANCED_CLUSTER"], var.cluster_type)
    error_message = "cluster_type must be BASIC_CLUSTER or ENHANCED_CLUSTER"
  }
}

variable "use_always_free" {
  description = "Use Always Free tier resources (ARM Ampere A1)"
  type        = bool
  default     = true
}

variable "node_image_id" {
  description = "OCID of node image (Oracle Linux 8 for ARM)"
  type        = string
  default     = ""  # Will be auto-selected if empty
}

variable "ssh_public_key" {
  description = "SSH public key for node access"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default = {
    Project     = "health-data-ai-platform"
    ManagedBy   = "terraform"
    Environment = "production"
  }
}
```

**File: `terraform/modules/kubernetes-cluster/oracle-oke/network.tf`**

```hcl
# Virtual Cloud Network (VCN)
resource "oci_core_vcn" "k8s_vcn" {
  compartment_id = var.compartment_id
  display_name   = "${var.cluster_name}-vcn"
  cidr_blocks    = [var.vcn_cidr]
  dns_label      = replace(var.cluster_name, "-", "")

  freeform_tags = var.tags
}

# Internet Gateway
resource "oci_core_internet_gateway" "k8s_igw" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-igw"
  enabled        = true

  freeform_tags = var.tags
}

# NAT Gateway (for private subnets)
resource "oci_core_nat_gateway" "k8s_nat" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-nat"

  freeform_tags = var.tags
}

# Service Gateway (for OCI services)
data "oci_core_services" "all_services" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

resource "oci_core_service_gateway" "k8s_svcgw" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-svcgw"

  services {
    service_id = data.oci_core_services.all_services.services[0].id
  }

  freeform_tags = var.tags
}

# Route Table for Public Subnet (Kubernetes API)
resource "oci_core_route_table" "public_route_table" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.k8s_igw.id
  }

  freeform_tags = var.tags
}

# Route Table for Private Subnet (Worker Nodes)
resource "oci_core_route_table" "private_route_table" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-private-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.k8s_nat.id
  }

  route_rules {
    destination       = data.oci_core_services.all_services.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.k8s_svcgw.id
  }

  freeform_tags = var.tags
}

# Security List for Kubernetes API Endpoint
resource "oci_core_security_list" "k8s_api_security_list" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-api-seclist"

  # Ingress: Allow Kubernetes API access (6443)
  ingress_security_rules {
    protocol    = "6"  # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "Kubernetes API access"

    tcp_options {
      min = 6443
      max = 6443
    }
  }

  # Ingress: Allow ICMP for path MTU discovery
  ingress_security_rules {
    protocol    = "1"  # ICMP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "ICMP path MTU discovery"
  }

  # Egress: Allow all outbound
  egress_security_rules {
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    description      = "Allow all outbound"
  }

  freeform_tags = var.tags
}

# Security List for Worker Nodes
resource "oci_core_security_list" "k8s_node_security_list" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-node-seclist"

  # Ingress: Allow all from VCN (pod-to-pod, node-to-node)
  ingress_security_rules {
    protocol    = "all"
    source      = var.vcn_cidr
    source_type = "CIDR_BLOCK"
    description = "Allow all intra-VCN traffic"
  }

  # Ingress: Allow SSH from anywhere (for debugging)
  ingress_security_rules {
    protocol    = "6"  # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "SSH access"

    tcp_options {
      min = 22
      max = 22
    }
  }

  # Ingress: Allow NodePort range (for LoadBalancer services)
  ingress_security_rules {
    protocol    = "6"  # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "NodePort range for LoadBalancer"

    tcp_options {
      min = 30000
      max = 32767
    }
  }

  # Egress: Allow all outbound
  egress_security_rules {
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    description      = "Allow all outbound"
  }

  freeform_tags = var.tags
}

# Security List for Load Balancer
resource "oci_core_security_list" "k8s_lb_security_list" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-lb-seclist"

  # Ingress: Allow HTTPS (443)
  ingress_security_rules {
    protocol    = "6"  # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "HTTPS traffic"

    tcp_options {
      min = 443
      max = 443
    }
  }

  # Ingress: Allow HTTP (80) for cert challenge
  ingress_security_rules {
    protocol    = "6"  # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "HTTP traffic (cert challenge)"

    tcp_options {
      min = 80
      max = 80
    }
  }

  # Egress: Allow all outbound
  egress_security_rules {
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    description      = "Allow all outbound"
  }

  freeform_tags = var.tags
}

# Subnet for Kubernetes API Endpoint (Public)
resource "oci_core_subnet" "k8s_api_subnet" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-api-subnet"
  cidr_block     = cidrsubnet(var.vcn_cidr, 8, 1)  # 10.0.1.0/24
  dns_label      = "api"

  route_table_id             = oci_core_route_table.public_route_table.id
  security_list_ids          = [oci_core_security_list.k8s_api_security_list.id]
  prohibit_public_ip_on_vnic = false
  prohibit_internet_ingress  = false

  freeform_tags = var.tags
}

# Subnet for Worker Nodes (Private)
resource "oci_core_subnet" "k8s_node_subnet" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-node-subnet"
  cidr_block     = cidrsubnet(var.vcn_cidr, 8, 2)  # 10.0.2.0/24
  dns_label      = "nodes"

  route_table_id             = oci_core_route_table.private_route_table.id
  security_list_ids          = [oci_core_security_list.k8s_node_security_list.id]
  prohibit_public_ip_on_vnic = false  # Set to true for private nodes
  prohibit_internet_ingress  = false

  freeform_tags = var.tags
}

# Subnet for Load Balancer (Public)
resource "oci_core_subnet" "k8s_lb_subnet" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-lb-subnet"
  cidr_block     = cidrsubnet(var.vcn_cidr, 8, 3)  # 10.0.3.0/24
  dns_label      = "lb"

  route_table_id             = oci_core_route_table.public_route_table.id
  security_list_ids          = [oci_core_security_list.k8s_lb_security_list.id]
  prohibit_public_ip_on_vnic = false
  prohibit_internet_ingress  = false

  freeform_tags = var.tags
}
```

**File: `terraform/modules/kubernetes-cluster/oracle-oke/main.tf`**

```hcl
# Get availability domains
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_id
}

# Get Oracle Linux 8 ARM image for nodes
data "oci_core_images" "oracle_linux_arm" {
  compartment_id           = var.compartment_id
  operating_system         = "Oracle Linux"
  operating_system_version = "8"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  filter {
    name   = "display_name"
    values = ["^([a-zA-z]+)-([a-zA-z]+)-([\\.0-9]+)-([\\.0-9-]+)$"]
    regex  = true
  }
}

# OKE Cluster
resource "oci_containerengine_cluster" "k8s_cluster" {
  compartment_id     = var.compartment_id
  name               = var.cluster_name
  vcn_id             = oci_core_vcn.k8s_vcn.id
  kubernetes_version = var.kubernetes_version
  type               = var.cluster_type

  endpoint_config {
    is_public_ip_enabled = true
    subnet_id            = oci_core_subnet.k8s_api_subnet.id
  }

  options {
    service_lb_subnet_ids = [oci_core_subnet.k8s_lb_subnet.id]

    add_ons {
      is_kubernetes_dashboard_enabled = false  # Deprecated
      is_tiller_enabled               = false  # Helm 2 (deprecated)
    }

    kubernetes_network_config {
      pods_cidr     = var.pod_cidr
      services_cidr = var.service_cidr
    }

    persistent_volume_config {
      freeform_tags = var.tags
    }

    service_lb_config {
      freeform_tags = var.tags
    }
  }

  freeform_tags = var.tags
}

# Node Pools
resource "oci_containerengine_node_pool" "node_pools" {
  count = length(var.node_pools)

  cluster_id         = oci_containerengine_cluster.k8s_cluster.id
  compartment_id     = var.compartment_id
  name               = "${var.cluster_name}-${var.node_pools[count.index].name}"
  kubernetes_version = var.kubernetes_version

  node_shape = var.use_always_free ? "VM.Standard.A1.Flex" : "VM.Standard.E4.Flex"

  node_shape_config {
    memory_in_gbs = var.node_pools[count.index].memory_gb
    ocpus         = var.node_pools[count.index].ocpu_count
  }

  node_source_details {
    image_id    = var.node_image_id != "" ? var.node_image_id : data.oci_core_images.oracle_linux_arm.images[0].id
    source_type = "IMAGE"
  }

  node_config_details {
    placement_configs {
      availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
      subnet_id          = oci_core_subnet.k8s_node_subnet.id
    }

    size = var.node_pools[count.index].node_count

    freeform_tags = merge(
      var.tags,
      {
        NodePool = var.node_pools[count.index].name
      }
    )
  }

  ssh_public_key = var.ssh_public_key

  initial_node_labels {
    key   = "pool"
    value = var.node_pools[count.index].name
  }

  freeform_tags = var.tags
}
```

**File: `terraform/modules/kubernetes-cluster/oracle-oke/storage.tf`**

```hcl
# Object Storage Bucket for Terraform State
resource "oci_objectstorage_bucket" "terraform_state" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "${var.cluster_name}-terraform-state"
  access_type    = "NoPublicAccess"

  versioning     = "Enabled"

  freeform_tags = merge(
    var.tags,
    {
      Purpose = "terraform-state"
    }
  )
}

# Object Storage Bucket for Velero Backups
resource "oci_objectstorage_bucket" "velero_backups" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "${var.cluster_name}-velero-backups"
  access_type    = "NoPublicAccess"

  versioning     = "Enabled"

  freeform_tags = merge(
    var.tags,
    {
      Purpose = "kubernetes-backups"
    }
  )
}

# Object Storage Bucket for Database Backups
resource "oci_objectstorage_bucket" "database_backups" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "${var.cluster_name}-database-backups"
  access_type    = "NoPublicAccess"

  versioning     = "Enabled"

  # Lifecycle policy: Delete backups older than 30 days
  retention_rules {
    display_name = "delete-old-backups"
    duration {
      time_amount = 30
      time_unit   = "DAYS"
    }
  }

  freeform_tags = merge(
    var.tags,
    {
      Purpose = "database-backups"
    }
  )
}

# Get object storage namespace
data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.compartment_id
}
```

**File: `terraform/modules/kubernetes-cluster/oracle-oke/outputs.tf`**

```hcl
output "cluster_id" {
  description = "OKE Cluster OCID"
  value       = oci_containerengine_cluster.k8s_cluster.id
}

output "cluster_name" {
  description = "OKE Cluster name"
  value       = oci_containerengine_cluster.k8s_cluster.name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = oci_containerengine_cluster.k8s_cluster.endpoints[0].public_endpoint
}

output "cluster_ca_certificate" {
  description = "Cluster CA certificate"
  value       = base64decode(oci_containerengine_cluster.k8s_cluster.kubernetes_network_config[0].cluster_ca_certificate)
  sensitive   = true
}

output "kubeconfig" {
  description = "Kubeconfig file content"
  value       = data.oci_containerengine_cluster_kube_config.cluster_kube_config.content
  sensitive   = true
}

output "vcn_id" {
  description = "VCN OCID"
  value       = oci_core_vcn.k8s_vcn.id
}

output "node_pool_ids" {
  description = "Node pool OCIDs"
  value       = oci_containerengine_node_pool.node_pools[*].id
}

output "object_storage_namespace" {
  description = "Object storage namespace"
  value       = data.oci_objectstorage_namespace.ns.namespace
}

output "terraform_state_bucket" {
  description = "Terraform state bucket name"
  value       = oci_objectstorage_bucket.terraform_state.name
}

output "velero_backup_bucket" {
  description = "Velero backup bucket name"
  value       = oci_objectstorage_bucket.velero_backups.name
}

output "database_backup_bucket" {
  description = "Database backup bucket name"
  value       = oci_objectstorage_bucket.database_backups.name
}

# Data source to get kubeconfig
data "oci_containerengine_cluster_kube_config" "cluster_kube_config" {
  cluster_id = oci_containerengine_cluster.k8s_cluster.id
}
```

### Step 4: Create Production Environment Configuration

**File: `terraform/environments/production/backend.tf`**

```hcl
terraform {
  backend "s3" {
    bucket                      = "health-platform-prod-terraform-state"
    key                         = "production/terraform.tfstate"
    region                      = "eu-amsterdam-1"
    endpoint                    = "https://<namespace>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    force_path_style            = true
  }
}

# Note: You'll need to create the bucket manually first, then uncomment this backend
# For first run, comment out this file and use local state
```

**File: `terraform/environments/production/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6.0"
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

module "kubernetes_cluster" {
  source = "../../modules/kubernetes-cluster/oracle-oke"

  compartment_id     = var.compartment_id
  cluster_name       = var.cluster_name
  region             = var.region
  kubernetes_version = var.kubernetes_version

  vcn_cidr     = var.vcn_cidr
  pod_cidr     = var.pod_cidr
  service_cidr = var.service_cidr

  node_pools = var.node_pools

  cluster_type    = var.cluster_type
  use_always_free = var.use_always_free

  ssh_public_key = file(var.ssh_public_key_path)

  tags = var.tags
}
```

**File: `terraform/environments/production/variables.tf`**

```hcl
# OCI Provider Configuration
variable "tenancy_ocid" {
  description = "OCI Tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI User OCID"
  type        = string
}

variable "fingerprint" {
  description = "OCI API Key Fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to OCI private key"
  type        = string
  default     = "~/.oci/oci_api_key.pem"
}

variable "region" {
  description = "OCI Region"
  type        = string
  default     = "eu-amsterdam-1"
}

variable "compartment_id" {
  description = "OCI Compartment OCID"
  type        = string
}

# Cluster Configuration
variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = string
  default     = "health-platform-prod"
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "v1.28.2"
}

variable "cluster_type" {
  description = "OKE cluster type (BASIC_CLUSTER is free)"
  type        = string
  default     = "BASIC_CLUSTER"
}

variable "use_always_free" {
  description = "Use Always Free tier resources"
  type        = bool
  default     = true
}

# Network Configuration
variable "vcn_cidr" {
  description = "CIDR block for VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "pod_cidr" {
  description = "CIDR for pod network"
  type        = string
  default     = "10.244.0.0/16"
}

variable "service_cidr" {
  description = "CIDR for service network"
  type        = string
  default     = "10.96.0.0/16"
}

# Node Pool Configuration
variable "node_pools" {
  description = "Node pool configurations"
  type = list(object({
    name         = string
    ocpu_count   = number
    memory_gb    = number
    node_count   = number
    auto_scale   = bool
    min_nodes    = number
    max_nodes    = number
  }))
  default = [
    {
      name         = "system-pool"
      ocpu_count   = 2
      memory_gb    = 12
      node_count   = 1
      auto_scale   = false
      min_nodes    = 1
      max_nodes    = 1
    },
    {
      name         = "app-pool"
      ocpu_count   = 1
      memory_gb    = 6
      node_count   = 2
      auto_scale   = false
      min_nodes    = 2
      max_nodes    = 2
    }
  ]
}

# SSH Configuration
variable "ssh_public_key_path" {
  description = "Path to SSH public key for node access"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "health-data-ai-platform"
    ManagedBy   = "terraform"
    Environment = "production"
  }
}
```

**File: `terraform/environments/production/terraform.tfvars`**

```hcl
# OCI Provider Configuration
# NOTE: Do NOT commit this file to Git - add to .gitignore
tenancy_ocid     = "ocid1.tenancy.oc1..example"
user_ocid        = "ocid1.user.oc1..example"
fingerprint      = "aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99"
private_key_path = "~/.oci/oci_api_key.pem"
region           = "eu-amsterdam-1"
compartment_id   = "ocid1.compartment.oc1..example"

# Cluster Configuration
cluster_name       = "health-platform-prod"
kubernetes_version = "v1.28.2"
cluster_type       = "BASIC_CLUSTER"  # FREE
use_always_free    = true             # Use ARM Ampere A1

# Network Configuration
vcn_cidr     = "10.0.0.0/16"
pod_cidr     = "10.244.0.0/16"
service_cidr = "10.96.0.0/16"

# Node Pools (Always Free: 4 OCPU, 24 GB RAM total)
node_pools = [
  {
    name         = "system-pool"
    ocpu_count   = 2
    memory_gb    = 12
    node_count   = 1
    auto_scale   = false
    min_nodes    = 1
    max_nodes    = 1
  },
  {
    name         = "app-pool"
    ocpu_count   = 1
    memory_gb    = 6
    node_count   = 2
    auto_scale   = false
    min_nodes    = 2
    max_nodes    = 2
  }
]

# SSH Configuration
ssh_public_key_path = "~/.ssh/id_rsa.pub"

# Tags
tags = {
  Project     = "health-data-ai-platform"
  ManagedBy   = "terraform"
  Environment = "production"
  CostCenter  = "always-free"
}
```

**File: `terraform/environments/production/outputs.tf`**

```hcl
output "cluster_id" {
  description = "OKE Cluster OCID"
  value       = module.kubernetes_cluster.cluster_id
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = module.kubernetes_cluster.cluster_endpoint
}

output "kubeconfig_instructions" {
  description = "Instructions to get kubeconfig"
  value       = <<-EOT
    To configure kubectl access:

    1. Save kubeconfig:
       terraform output -raw kubeconfig > ~/.kube/config-oke

    2. Set KUBECONFIG environment variable:
       export KUBECONFIG=~/.kube/config-oke

    3. Test access:
       kubectl get nodes
  EOT
}

output "kubeconfig" {
  description = "Kubeconfig file content"
  value       = module.kubernetes_cluster.kubeconfig
  sensitive   = true
}

output "vcn_id" {
  description = "VCN OCID"
  value       = module.kubernetes_cluster.vcn_id
}

output "backup_buckets" {
  description = "Object storage bucket names for backups"
  value = {
    terraform_state  = module.kubernetes_cluster.terraform_state_bucket
    velero_backups   = module.kubernetes_cluster.velero_backup_bucket
    database_backups = module.kubernetes_cluster.database_backup_bucket
  }
}
```

---

## Testing & Validation

### Step 5: Provision the Cluster

```bash
# 1. Navigate to production environment
cd terraform/environments/production

# 2. Initialize Terraform
terraform init

# 3. Validate configuration
terraform validate

# 4. Plan deployment (review changes)
terraform plan

# 5. Apply configuration
terraform apply

# Expected output:
# - OKE cluster created
# - 3 nodes provisioned (1x 2 OCPU, 2x 1 OCPU)
# - VCN and networking configured
# - Object storage buckets created

# 6. Save kubeconfig
terraform output -raw kubeconfig > ~/.kube/config-oke
chmod 600 ~/.kube/config-oke
export KUBECONFIG=~/.kube/config-oke

# 7. Verify cluster access
kubectl cluster-info
kubectl get nodes

# Expected output:
# NAME                              STATUS   ROLES   AGE   VERSION
# oke-system-pool-xxxxx             Ready    node    5m    v1.28.2
# oke-app-pool-xxxxx-0              Ready    node    5m    v1.28.2
# oke-app-pool-xxxxx-1              Ready    node    5m    v1.28.2
```

### Step 6: Verify Resource Allocation

```bash
# Check node resources
kubectl describe nodes

# Expected output for system-pool node:
# Capacity:
#   cpu:                2
#   memory:             12238Mi
#   pods:               110

# Expected output for app-pool nodes (each):
# Capacity:
#   cpu:                1
#   memory:             6119Mi
#   pods:               110

# Total capacity: 4 CPU, 24 GB RAM ✅
```

---

## Success Criteria

- [ ] OKE cluster provisioned successfully
- [ ] 3 nodes running (1x 2 OCPU, 2x 1 OCPU)
- [ ] kubectl can access cluster
- [ ] All nodes in Ready state
- [ ] VCN and subnets created
- [ ] Object storage buckets created (3 buckets)
- [ ] Total cost: $0 (within Always Free tier)
- [ ] Terraform state working (local or remote)

---

## Troubleshooting

### Issue: "Service limit exceeded"

```bash
# Solution: Request service limit increase
# Oracle Console → Governance → Limits, Quotas and Usage
# Request increase for:
# - Compute: ARM CPU cores (need 4)
# - Block Volumes: 200 GB
```

### Issue: "Insufficient capacity"

```bash
# Solution: Try different availability domain
# Modify placement_configs in node_pool to use different AD
data.oci_identity_availability_domains.ads.availability_domains[1].name
```

### Issue: "Cannot connect to cluster"

```bash
# Verify kubeconfig
terraform output -raw kubeconfig

# Check OCI CLI is configured
oci iam region list

# Regenerate kubeconfig via OCI CLI
oci ce cluster create-kubeconfig \
  --cluster-id <cluster-ocid> \
  --file ~/.kube/config-oke \
  --region eu-amsterdam-1
```

---

## Next Steps

1. ✅ **Module 1 Complete**: OKE cluster is running
2. **Proceed to Module 2**: Deploy infrastructure Helm charts (PostgreSQL, Redis, MinIO, RabbitMQ)
3. **Set up kubectl context** for other team members
4. **Document cluster details** for reference

---

## Appendix: Terraform Commands Reference

```bash
# Initialize Terraform
terraform init

# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Plan changes
terraform plan -out=tfplan

# Apply changes
terraform apply tfplan

# Show current state
terraform show

# List resources
terraform state list

# Destroy infrastructure (CAREFUL!)
terraform destroy

# Get specific output
terraform output -raw kubeconfig

# Refresh state
terraform refresh

# Import existing resource
terraform import module.kubernetes_cluster.oci_containerengine_cluster.k8s_cluster <ocid>
```

---

**Module 1 Complete**: Oracle OKE cluster provisioning with Terraform
