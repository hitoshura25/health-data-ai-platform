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
  description = "Kubernetes version (check OCI console for currently supported versions)"
  type        = string
  default     = "v1.28.2" # NOTE: Verify this version is still supported by OKE before deployment
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
  description = "Node pool configurations (fixed size for Always Free tier)"
  type = list(object({
    name       = string
    ocpu_count = number
    memory_gb  = number
    node_count = number
  }))
  default = [
    {
      name       = "system-pool"
      ocpu_count = 2
      memory_gb  = 12
      node_count = 1
    },
    {
      name       = "app-pool"
      ocpu_count = 1
      memory_gb  = 6
      node_count = 2
    }
  ]

  validation {
    condition = sum([for pool in var.node_pools : pool.ocpu_count * pool.node_count]) <= 4
    error_message = "Total OCPUs across all node pools cannot exceed 4 (Always Free tier limit)"
  }

  validation {
    condition = sum([for pool in var.node_pools : pool.memory_gb * pool.node_count]) <= 24
    error_message = "Total memory across all node pools cannot exceed 24 GB (Always Free tier limit)"
  }
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
  default     = "" # Will be auto-selected if empty
}

variable "ssh_public_key" {
  description = "SSH public key for node access"
  type        = string
}

# Security Configuration
variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH to worker nodes. Use restrictive CIDRs for production"
  type        = list(string)
  default     = ["0.0.0.0/0"] # WARNING: Allow from anywhere (not recommended for production)
}

variable "allowed_api_cidrs" {
  description = "CIDR blocks allowed to access Kubernetes API. Use restrictive CIDRs for production"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Allow from anywhere (standard for managed K8s, but can be restricted)
}

variable "use_private_nodes" {
  description = "Use private nodes (no public IPs). Nodes will use NAT gateway for outbound traffic"
  type        = bool
  default     = false # Set to true for enhanced security in production
}

# Network Subnet Offsets
variable "api_subnet_offset" {
  description = "Subnet offset for Kubernetes API endpoint subnet"
  type        = number
  default     = 1
}

variable "node_subnet_offset" {
  description = "Subnet offset for worker node subnet"
  type        = number
  default     = 2
}

variable "lb_subnet_offset" {
  description = "Subnet offset for load balancer subnet"
  type        = number
  default     = 3
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
