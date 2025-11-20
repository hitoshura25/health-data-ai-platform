#!/bin/bash
# List all available backups
# Usage: ./list-backups.sh

set -e

echo "==========================================="
echo "Health Data AI Platform - Backup Inventory"
echo "==========================================="

# Check if velero is installed
if ! command -v velero &> /dev/null; then
    echo "WARNING: velero CLI not found"
else
    echo ""
    echo "Velero Backups:"
    echo "-------------------------------------------"
    velero backup get || echo "No Velero backups found"
fi

echo ""
echo "Database Backup Jobs:"
echo "-------------------------------------------"

echo ""
echo "PostgreSQL Health Data:"
kubectl get cronjob postgresql-health-backup -n health-data -o wide 2>/dev/null || echo "  CronJob not found"
kubectl get jobs -n health-data -l app=postgresql-backup,database=health-data --sort-by=.status.startTime | tail -5 2>/dev/null || echo "  No recent jobs"

echo ""
echo "PostgreSQL Auth:"
kubectl get cronjob postgresql-auth-backup -n health-auth -o wide 2>/dev/null || echo "  CronJob not found"
kubectl get jobs -n health-auth -l app=postgresql-backup,database=webauthn-auth --sort-by=.status.startTime | tail -5 2>/dev/null || echo "  No recent jobs"

echo ""
echo "MinIO Data Lake:"
kubectl get cronjob minio-backup -n health-data -o wide 2>/dev/null || echo "  CronJob not found"
kubectl get jobs -n health-data -l app=minio-backup --sort-by=.status.startTime | tail -5 2>/dev/null || echo "  No recent jobs"

echo ""
echo "RabbitMQ:"
kubectl get cronjob rabbitmq-backup -n health-data -o wide 2>/dev/null || echo "  CronJob not found"
kubectl get jobs -n health-data -l app=rabbitmq-backup --sort-by=.status.startTime | tail -5 2>/dev/null || echo "  No recent jobs"

echo ""
echo "Backup Verification:"
echo "-------------------------------------------"
kubectl get cronjob backup-verification -n velero -o wide 2>/dev/null || echo "  CronJob not found"
kubectl get jobs -n velero -l app=backup-verification --sort-by=.status.startTime | tail -3 2>/dev/null || echo "  No recent jobs"

echo ""
echo "==========================================="
echo ""
echo "To create a manual backup:"
echo "  ./backup-all.sh"
echo ""
echo "To restore from a backup:"
echo "  ./restore-cluster.sh <backup-name>"
echo ""
echo "To restore a specific database:"
echo "  ./restore-database.sh <database-type> <backup-file>"
echo ""
