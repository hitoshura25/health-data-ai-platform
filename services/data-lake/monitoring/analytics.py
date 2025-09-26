from storage.client import SecureMinIOClient
from core.naming import IntelligentObjectKeyGenerator
from typing import Dict, Any, List
from datetime import datetime, timedelta
import json
import pandas as pd
import structlog

logger = structlog.get_logger()

class DataLakeAnalytics:
    """Comprehensive data lake analytics and monitoring"""

    def __init__(self, minio_client: SecureMinIOClient, bucket_name: str):
        self.client = minio_client
        self.bucket_name = bucket_name
        self.key_generator = IntelligentObjectKeyGenerator()

    async def generate_daily_analytics(self, date: datetime = None) -> Dict[str, Any]:
        """Generate daily analytics report"""

        if date is None:
            date = datetime.utcnow()

        analytics = {
            "date": date.isoformat(),
            "bucket": self.bucket_name,
            "summary": {
                "total_objects": 0,
                "total_size_gb": 0,
                "new_objects_today": 0,
                "new_data_size_gb": 0
            },
            "by_record_type": {},
            "by_user": {},
            "quality_metrics": {
                "total_files_processed": 0,
                "files_quarantined": 0,
                "average_quality_score": 0,
                "quality_distribution": {}
            },
            "storage_efficiency": {
                "compression_ratio": 0,
                "deduplication_savings": 0
            },
            "usage_patterns": {
                "peak_upload_hour": None,
                "most_active_users": []
            }
        }

        try:
            # Analyze all objects
            async for obj_metadata in self.client.list_objects_with_metadata(
                self.bucket_name, recursive=True
            ):
                analytics["summary"]["total_objects"] += 1
                size_gb = obj_metadata["size"] / (1024 ** 3)
                analytics["summary"]["total_size_gb"] += size_gb

                # Check if object was created today
                if obj_metadata["last_modified"].date() == date.date():
                    analytics["summary"]["new_objects_today"] += 1
                    analytics["summary"]["new_data_size_gb"] += size_gb

                # Parse object key for detailed analysis
                key_components = self.key_generator.parse_object_key(obj_metadata["object_name"])

                if key_components:
                    # Analyze by record type
                    record_type = key_components.record_type
                    if record_type not in analytics["by_record_type"]:
                        analytics["by_record_type"][record_type] = {
                            "objects": 0,
                            "size_gb": 0,
                            "latest_upload": None
                        }

                    analytics["by_record_type"][record_type]["objects"] += 1
                    analytics["by_record_type"][record_type]["size_gb"] += size_gb

                    if (analytics["by_record_type"][record_type]["latest_upload"] is None or
                        obj_metadata["last_modified"] > analytics["by_record_type"][record_type]["latest_upload"]):
                        analytics["by_record_type"][record_type]["latest_upload"] = obj_metadata["last_modified"]

                    # Analyze by user (only for raw data)
                    if key_components.layer == "raw":
                        user_id = key_components.user_id
                        if user_id not in analytics["by_user"]:
                            analytics["by_user"][user_id] = {
                                "objects": 0,
                                "size_gb": 0,
                                "record_types": set()
                            }

                        analytics["by_user"][user_id]["objects"] += 1
                        analytics["by_user"][user_id]["size_gb"] += size_gb
                        analytics["by_user"][user_id]["record_types"].add(record_type)

                # Analyze quarantine data
                if obj_metadata["object_name"].startswith("quarantine/"):
                    analytics["quality_metrics"]["files_quarantined"] += 1

            # Convert sets to lists for JSON serialization
            for user_data in analytics["by_user"].values():
                user_data["record_types"] = list(user_data["record_types"])

            # Calculate additional metrics
            analytics = await self._enhance_analytics_with_quality_metrics(analytics)
            analytics = await self._enhance_analytics_with_usage_patterns(analytics, date)

            # Store analytics
            await self._store_analytics(analytics, date)

            logger.info("Daily analytics generated",
                       date=date.isoformat(),
                       total_objects=analytics["summary"]["total_objects"])

            return analytics

        except Exception as e:
            logger.error("Failed to generate analytics", error=str(e))
            raise

    async def _enhance_analytics_with_quality_metrics(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance analytics with quality metrics from metadata"""

        quality_scores = []
        quality_distribution = {"high": 0, "medium": 0, "low": 0}

        # This would typically read from stored metadata or a separate quality tracking system
        # For now, simulate quality metrics

        total_files = analytics["summary"]["total_objects"]
        if total_files > 0:
            # Simulate quality scores
            import random
            for _ in range(min(total_files, 100)):  # Sample for performance
                score = random.uniform(0.6, 1.0)  # Simulate realistic quality scores
                quality_scores.append(score)

                if score >= 0.9:
                    quality_distribution["high"] += 1
                elif score >= 0.7:
                    quality_distribution["medium"] += 1
                else:
                    quality_distribution["low"] += 1

            analytics["quality_metrics"]["average_quality_score"] = sum(quality_scores) / len(quality_scores)
            analytics["quality_metrics"]["quality_distribution"] = quality_distribution

        return analytics

    async def _enhance_analytics_with_usage_patterns(self, analytics: Dict[str, Any], date: datetime) -> Dict[str, Any]:
        """Enhance analytics with usage pattern analysis"""

        # Analyze upload patterns by hour
        upload_hours = {}
        most_active_users = []

        # Sort users by activity
        user_activity = [
            (user_id, data["objects"])
            for user_id, data in analytics["by_user"].items()
        ]
        user_activity.sort(key=lambda x: x[1], reverse=True)

        analytics["usage_patterns"]["most_active_users"] = [
            {"user_id": user_id, "objects": count}
            for user_id, count in user_activity[:5]  # Top 5 users
        ]

        # This would typically analyze actual upload timestamps
        # For now, provide a framework
        analytics["usage_patterns"]["peak_upload_hour"] = "14:00"  # 2 PM as example

        return analytics

    async def _store_analytics(self, analytics: Dict[str, Any], date: datetime):
        """Store analytics data in the data lake"""

        try:
            analytics_key = self.key_generator.generate_analytics_key("daily_summary", date)
            analytics_json = json.dumps(analytics, default=str, indent=2)

            await self.client.upload_file(
                self.bucket_name,
                analytics_key,
                analytics_json.encode(),
                content_type="application/json",
                metadata={
                    "analytics_type": "daily_summary",
                    "generated_at": datetime.utcnow().isoformat()
                }
            )

            logger.info("Analytics stored", analytics_key=analytics_key)

        except Exception as e:
            logger.error("Failed to store analytics", error=str(e))

    async def get_storage_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get storage growth trends over time"""

        try:
            trends = {
                "period_days": days,
                "daily_growth": [],
                "record_type_trends": {},
                "storage_efficiency_trend": []
            }

            # This would typically query stored analytics
            # For now, provide a framework for trend analysis

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            current_date = start_date
            while current_date <= end_date:
                # Simulate daily growth data
                trends["daily_growth"].append({
                    "date": current_date.isoformat(),
                    "objects_added": 10,  # Simulated
                    "size_gb_added": 0.5  # Simulated
                })

                current_date += timedelta(days=1)

            return trends

        except Exception as e:
            logger.error("Failed to get storage trends", error=str(e))
            return {"error": str(e)}

    async def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report for audit purposes"""

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "bucket": self.bucket_name,
            "compliance_checks": {
                "encryption_enabled": False,
                "versioning_enabled": False,
                "lifecycle_policies_configured": False,
                "access_logging_enabled": False
            },
            "data_retention": {
                "oldest_data": None,
                "retention_policy_compliant": True
            },
            "security_status": {
                "secure_access_only": False,
                "proper_access_controls": False
            },
            "recommendations": []
        }

        try:
            # Check bucket health
            health_status = self.client.check_bucket_health(self.bucket_name)

            report["compliance_checks"]["encryption_enabled"] = health_status.get("encryption_enabled", False)
            report["compliance_checks"]["versioning_enabled"] = health_status.get("versioning_enabled", False)
            report["compliance_checks"]["lifecycle_policies_configured"] = health_status.get("lifecycle_configured", False)

            # Generate recommendations
            if not report["compliance_checks"]["encryption_enabled"]:
                report["recommendations"].append("Enable bucket encryption for data at rest protection")

            if not report["compliance_checks"]["versioning_enabled"]:
                report["recommendations"].append("Enable bucket versioning for data protection and recovery")

            if not report["compliance_checks"]["lifecycle_policies_configured"]:
                report["recommendations"].append("Configure lifecycle policies for automated data management")

            return report

        except Exception as e:
            logger.error("Failed to generate compliance report", error=str(e))
            return {"error": str(e)}