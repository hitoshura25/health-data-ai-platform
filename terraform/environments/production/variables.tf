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
    name       = string
    ocpu_count = number
    memory_gb  = number
    node_count = number
    auto_scale = bool
    min_nodes  = number
    max_nodes  = number
  }))
  default = [
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
