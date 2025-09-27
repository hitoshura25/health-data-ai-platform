# Data Lake Integration Tests

This directory contains integration tests for the data lake service.

## Running the tests

1.  **Start the MinIO service:**

    ```bash
    docker-compose up -d minio
    ```

2.  **Set the environment variables:**

    ```bash
    export DATALAKE_MINIO_ENDPOINT=localhost:9000
    export DATALAKE_MINIO_ACCESS_KEY=minioadmin
    export DATALAKE_MINIO_SECRET_KEY=minioadmin
    ```

3.  **Run the tests:**

    ```bash
    pytest
    ```

4.  **Stop the MinIO service:**

    ```bash
    docker-compose down
    ```
