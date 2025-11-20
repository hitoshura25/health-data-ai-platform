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
       chmod 600 ~/.kube/config-oke

    2. Set KUBECONFIG environment variable:
       export KUBECONFIG=~/.kube/config-oke

    3. Test access:
       kubectl get nodes

    4. (Optional) Merge with existing kubeconfig:
       KUBECONFIG=~/.kube/config:~/.kube/config-oke kubectl config view --flatten > ~/.kube/config-merged
       mv ~/.kube/config-merged ~/.kube/config
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

output "object_storage_namespace" {
  description = "Object storage namespace (needed for backend configuration)"
  value       = module.kubernetes_cluster.object_storage_namespace
}

output "resource_summary" {
  description = "Summary of provisioned resources"
  value       = <<-EOT
    ===================================================================
    OKE Cluster Successfully Provisioned
    ===================================================================

    Cluster Details:
    - Name: ${module.kubernetes_cluster.cluster_name}
    - Type: Always Free tier (BASIC_CLUSTER)
    - Kubernetes Version: ${var.kubernetes_version}
    - Region: eu-amsterdam-1 (100% renewable energy)

    Resources:
    - Nodes: 3 (1x 2 OCPU, 2x 1 OCPU) = 4 vCPU, 24 GB RAM
    - VCN: ${module.kubernetes_cluster.vcn_id}
    - API Endpoint: ${module.kubernetes_cluster.cluster_endpoint}

    Storage Buckets:
    - Terraform State: ${module.kubernetes_cluster.terraform_state_bucket}
    - Velero Backups: ${module.kubernetes_cluster.velero_backup_bucket}
    - Database Backups: ${module.kubernetes_cluster.database_backup_bucket}

    Next Steps:
    1. Configure kubectl (see kubeconfig_instructions output)
    2. Verify nodes: kubectl get nodes
    3. Deploy Helm charts (Module 2-4)
    4. Set up observability stack (Module 5)

    Cost: $0/month (within Oracle Always Free tier limits)
    ===================================================================
  EOT
}
