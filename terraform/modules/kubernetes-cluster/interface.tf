# Cloud-Agnostic Kubernetes Cluster Interface
#
# This file defines the standard contract/interface for Kubernetes cluster modules
# across different cloud providers (Oracle, GCP, AWS, etc.).
#
# NOTE: This is a DOCUMENTATION/TEMPLATE file, not a functional Terraform module.
# Actual implementations are in provider-specific subdirectories:
#   - oracle-oke/   (Oracle Kubernetes Engine)
#   - gcp-gke/      (Google Kubernetes Engine - future)
#   - aws-eks/      (Amazon Elastic Kubernetes Service - future)
#
# The outputs defined here have placeholder values and will be overridden by
# provider-specific implementations. This file serves to document the expected
# inputs and outputs that all provider implementations should support to maintain
# cloud portability.

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
