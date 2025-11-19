# Data source to get kubeconfig
data "oci_containerengine_cluster_kube_config" "cluster_kube_config" {
  cluster_id = oci_containerengine_cluster.k8s_cluster.id
}

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
