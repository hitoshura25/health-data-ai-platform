# Cloud-Agnostic Kubernetes Cluster Interface
# Defines standard interface for all cloud providers (Oracle, GCP, AWS)

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
    name       = string
    ocpu_count = number
    memory_gb  = number
    node_count = number
    auto_scale = bool
    min_nodes  = number
    max_nodes  = number
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
  value       = "" # Implemented by provider module
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
