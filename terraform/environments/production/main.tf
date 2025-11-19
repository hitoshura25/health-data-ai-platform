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
