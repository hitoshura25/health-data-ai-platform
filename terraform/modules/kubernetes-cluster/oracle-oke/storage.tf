# Get object storage namespace
data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.compartment_id
}

# Object Storage Bucket for Terraform State
resource "oci_objectstorage_bucket" "terraform_state" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "${var.cluster_name}-terraform-state"
  access_type    = "NoPublicAccess"

  versioning = "Enabled"

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

  versioning = "Enabled"

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

  versioning = "Enabled"

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
