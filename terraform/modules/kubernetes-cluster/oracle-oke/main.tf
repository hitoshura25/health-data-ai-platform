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
    values = ["^([a-zA-Z]+)-([a-zA-Z]+)-([\\.0-9]+)-([\\.0-9-]+)$"]
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
      is_kubernetes_dashboard_enabled = false # Deprecated
      is_tiller_enabled               = false # Helm 2 (deprecated)
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
      subnet_id           = oci_core_subnet.k8s_node_subnet.id
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
