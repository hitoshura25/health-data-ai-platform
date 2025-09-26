# Data Lake Service

This service provides an intelligent object storage system for health data using MinIO.

## Features

- **Intelligent Object Naming:** Smart naming conventions for efficient querying.
- **Automated Lifecycle Management:** Built-in policies for data tiering and retention.
- **Data Quality Validation:** Application-level validation with quality scoring and automatic quarantine.
- **Security:** Encryption at rest, access controls, and audit logging.

## Setup

1.  **Install dependencies:** `pip install -r requirements.txt`
2.  **Start MinIO:** `docker-compose up -d minio`
3.  **Setup bucket:** `python deployment/scripts/setup_bucket.py`

## Server-Side Encryption (SSE)

The server-side encryption for the local MinIO setup is configured using a secret key. The implementation is based on the following resource:

- [MinIO Server-Side Encryption with Docker Compose](https://medium.com/@murisuu/self-host-s3-minio-docker-compose-setup-48588b2f9bcd)