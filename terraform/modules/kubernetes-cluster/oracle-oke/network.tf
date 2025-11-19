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
    protocol    = "6" # TCP
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
    protocol    = "1" # ICMP
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
    protocol    = "6" # TCP
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
    protocol    = "6" # TCP
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
    protocol    = "6" # TCP
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
    protocol    = "6" # TCP
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
  cidr_block     = cidrsubnet(var.vcn_cidr, 8, 1) # 10.0.1.0/24
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
  cidr_block     = cidrsubnet(var.vcn_cidr, 8, 2) # 10.0.2.0/24
  dns_label      = "nodes"

  route_table_id             = oci_core_route_table.private_route_table.id
  security_list_ids          = [oci_core_security_list.k8s_node_security_list.id]
  prohibit_public_ip_on_vnic = false # Set to true for private nodes
  prohibit_internet_ingress  = false

  freeform_tags = var.tags
}

# Subnet for Load Balancer (Public)
resource "oci_core_subnet" "k8s_lb_subnet" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.k8s_vcn.id
  display_name   = "${var.cluster_name}-lb-subnet"
  cidr_block     = cidrsubnet(var.vcn_cidr, 8, 3) # 10.0.3.0/24
  dns_label      = "lb"

  route_table_id             = oci_core_route_table.public_route_table.id
  security_list_ids          = [oci_core_security_list.k8s_lb_security_list.id]
  prohibit_public_ip_on_vnic = false
  prohibit_internet_ingress  = false

  freeform_tags = var.tags
}
