from minio import Minio
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration
from minio.commonconfig import Filter
from datetime import datetime, timedelta
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()

class DataLifecycleManager:
    """Manage data lifecycle with MinIO's native policies"""

    def __init__(self, minio_client: Minio):
        self.client = minio_client

    def setup_lifecycle_policies(self, bucket_name: str, config: Dict[str, Any]):
        """Configure comprehensive lifecycle policies"""

        rules = []

        # Raw data lifecycle: Archive and eventually delete
        raw_data_rule = Rule(
            rule_id="raw_data_lifecycle",
            status="Enabled",
            rule_filter=Filter(prefix="raw/"),
            expiration=Expiration(days=config.get('raw_data_expiration_days', 2555))  # 7 years
        )
        rules.append(raw_data_rule)

        # Processed data lifecycle: Keep accessible longer
        processed_data_rule = Rule(
            rule_id="processed_data_lifecycle",
            status="Enabled",
            rule_filter=Filter(prefix="processed/"),
            expiration=Expiration(days=config.get('processed_data_expiration_days', 3650))  # 10 years
        )
        rules.append(processed_data_rule)

        # Quarantine data: Delete quickly
        quarantine_rule = Rule(
            rule_id="quarantine_cleanup",
            status="Enabled",
            rule_filter=Filter(prefix="quarantine/"),
            expiration=Expiration(days=config.get('quarantine_retention_days', 30))
        )
        rules.append(quarantine_rule)

        # Analytics data: Short retention
        analytics_rule = Rule(
            rule_id="analytics_cleanup",
            status="Enabled",
            rule_filter=Filter(prefix="analytics/"),
            expiration=Expiration(days=365)  # 1 year
        )
        rules.append(analytics_rule)

        # Apply lifecycle configuration
        lifecycle_config = LifecycleConfig(rules)

        try:
            self.client.set_bucket_lifecycle(bucket_name, lifecycle_config)
            logger.info("Lifecycle policies configured successfully", bucket=bucket_name)

        except Exception as e:
            logger.error("Failed to configure lifecycle policies", error=str(e))
            raise

    def get_lifecycle_status(self, bucket_name: str) -> Dict[str, Any]:
        """Get current lifecycle configuration"""
        try:
            lifecycle_config = self.client.get_bucket_lifecycle(bucket_name)

            status = {
                "bucket": bucket_name,
                "rules": [],
                "total_rules": len(lifecycle_config.rules)
            }

            for rule in lifecycle_config.rules:
                rule_info = {
                    "id": rule.rule_id,
                    "status": rule.status,
                    "prefix": getattr(rule.rule_filter, 'prefix', None),
                    "transitions": [],
                    "expiration_days": rule.expiration_days
                }

                if rule.transitions:
                    for transition in rule.transitions:
                        rule_info["transitions"].append({
                            "days": transition.days,
                            "storage_class": transition.storage_class
                        })

                status["rules"].append(rule_info)

            return status

        except Exception as e:
            logger.error("Failed to get lifecycle status", error=str(e))
            return {"error": str(e)}

    async def estimate_storage_costs(self, bucket_name: str) -> Dict[str, Any]:
        """Estimate storage costs based on lifecycle policies"""
        # This would integrate with cloud provider APIs for actual cost estimation
        # For now, provide a framework for cost analysis

        try:
            objects = self.client.list_objects(bucket_name, recursive=True)

            cost_analysis = {
                "total_objects": 0,
                "total_size_gb": 0,
                "by_prefix": {},
                "estimated_monthly_cost_usd": 0,
                "cost_breakdown": {
                    "standard": {"objects": 0, "size_gb": 0, "cost_usd": 0},
                    "glacier": {"objects": 0, "size_gb": 0, "cost_usd": 0},
                    "deep_archive": {"objects": 0, "size_gb": 0, "cost_usd": 0}
                }
            }

            # Cost per GB per month (example rates)
            storage_costs = {
                "standard": 0.023,  # $0.023 per GB/month
                "glacier": 0.004,   # $0.004 per GB/month
                "deep_archive": 0.00099  # $0.00099 per GB/month
            }

            for obj in objects:
                cost_analysis["total_objects"] += 1
                size_gb = obj.size / (1024 ** 3)
                cost_analysis["total_size_gb"] += size_gb

                # Determine prefix
                prefix = obj.object_name.split('/')[0]
                if prefix not in cost_analysis["by_prefix"]:
                    cost_analysis["by_prefix"][prefix] = {
                        "objects": 0,
                        "size_gb": 0
                    }

                cost_analysis["by_prefix"][prefix]["objects"] += 1
                cost_analysis["by_prefix"][prefix]["size_gb"] += size_gb

                # Estimate storage class based on age and prefix
                obj_age_days = (datetime.utcnow() - obj.last_modified).days
                storage_class = self._estimate_storage_class(prefix, obj_age_days)

                cost_analysis["cost_breakdown"][storage_class]["objects"] += 1
                cost_analysis["cost_breakdown"][storage_class]["size_gb"] += size_gb
                cost_analysis["cost_breakdown"][storage_class]["cost_usd"] += size_gb * storage_costs[storage_class]

            # Calculate total estimated cost
            cost_analysis["estimated_monthly_cost_usd"] = sum(
                breakdown["cost_usd"] for breakdown in cost_analysis["cost_breakdown"].values()
            )

            return cost_analysis

        except Exception as e:
            logger.error("Failed to estimate storage costs", error=str(e))
            return {"error": str(e)}

    def _estimate_storage_class(self, prefix: str, age_days: int) -> str:
        """Estimate current storage class based on prefix and age"""
        if prefix == "raw":
            if age_days >= 365:
                return "deep_archive"
            elif age_days >= 90:
                return "glacier"
            else:
                return "standard"
        elif prefix == "processed":
            if age_days >= 180:
                return "glacier"
            else:
                return "standard"
        else:
            return "standard"