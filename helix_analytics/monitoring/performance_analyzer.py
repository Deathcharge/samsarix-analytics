"""
Performance Analyzer - Helix Collective v17.2
Advanced performance analysis with bottleneck detection and optimization recommendations
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.backend.core.performance_profiler import profiler
from apps.backend.monitoring.metrics import MetricsRegistry

logger = logging.getLogger(__name__)


# Safe accessor for database profiler metrics
def _get_db_profiler():
    """Safely get database profiler or return None."""
    try:
        # Database profiler is part of the main profiler system
        # Import with alias to avoid reimport warning
        from apps.backend.core.performance_profiler import profiler

        return profiler
    except (ImportError, AttributeError):
        logger.debug("Database profiler not available")
        return None


# Safe accessor for agent orchestrator metrics
def _get_orchestrator():
    """Safely get orchestrator or return None."""
    try:
        from apps.backend.agents.agent_orchestrator import orchestrator

        return orchestrator
    except ImportError:
        return None


class PerformanceAnalyzer:
    """
    Advanced performance analysis system with bottleneck detection
    and automated optimization recommendations
    """

    def __init__(self, metrics_registry: MetricsRegistry | None = None):
        self.metrics = metrics_registry or MetricsRegistry()
        self.analysis_window = timedelta(minutes=5)
        self.baseline_period = timedelta(hours=1)

        # Performance thresholds
        self.cpu_threshold = 80.0
        self.memory_threshold = 85.0
        self.response_time_threshold = 2.0  # seconds
        self.error_rate_threshold = 5.0  # percent

        # Analysis results with type annotations
        self.bottlenecks: list[dict[str, Any]] = []
        self.recommendations: list[str] = []
        self.performance_trends: dict[str, list[Any]] = defaultdict(list)

        logger.info("Performance Analyzer initialized")

    async def analyze_system_performance(self) -> dict[str, Any]:
        """
        Comprehensive system performance analysis

        Returns:
            Dict containing performance metrics and recommendations
        """
        try:
            current_metrics = await self._gather_current_metrics()

            # Analyze bottlenecks
            bottlenecks = await self._identify_bottlenecks(current_metrics)

            # Generate recommendations
            recommendations = await self._generate_recommendations(bottlenecks, current_metrics)

            # Update trends
            self._update_performance_trends(current_metrics)

            analysis_result = {
                "timestamp": datetime.now(UTC),
                "overall_score": self._calculate_performance_score(current_metrics),
                "current_metrics": current_metrics,
                "bottlenecks": bottlenecks,
                "recommendations": recommendations,
                "trends": dict(self.performance_trends),
            }

            logger.info(
                "Performance analysis completed - Score: %.2f",
                analysis_result["overall_score"],
            )
            return analysis_result

        except Exception as e:
            logger.error("Performance analysis failed: %s", str(e))
            return {
                "timestamp": datetime.now(UTC),
                "error": type(e).__name__,
                "overall_score": 0.0,
            }

    async def _gather_current_metrics(self) -> dict[str, Any]:
        """Gather current system metrics"""
        metrics = {}

        try:
            cpu_usage = profiler.get_cpu_usage()
            metrics["cpu"] = {
                "usage_percent": cpu_usage,
                "cores": profiler.get_cpu_count(),
                "load_average": profiler.get_load_average(),
            }

            # Memory metrics
            memory_info = profiler.get_memory_usage()
            metrics["memory"] = {
                "used_percent": memory_info.get("percent", 0),
                "used_mb": memory_info.get("used", 0) / 1024 / 1024,
                "available_mb": memory_info.get("available", 0) / 1024 / 1024,
                "total_mb": memory_info.get("total", 0) / 1024 / 1024,
            }

            # Database metrics
            db_metrics = await self._get_database_metrics()
            metrics["database"] = db_metrics

            # API response times
            api_metrics = await self._get_api_metrics()
            metrics["api"] = api_metrics

            # Agent performance
            agent_metrics = await self._get_agent_metrics()
            metrics["agents"] = agent_metrics

        except Exception as e:
            logger.error("Failed to gather metrics: %s", str(e))

        return metrics

    async def _get_database_metrics(self) -> dict[str, Any]:
        """Get database performance metrics"""
        try:
            db_prof = _get_db_profiler()
            if db_prof is None:
                return {
                    "connection_count": 0,
                    "query_count": 0,
                    "slow_queries": 0,
                    "average_query_time": 0.0,
                    "connection_pool_size": 0,
                }

            db_metrics = {
                "connection_count": db_prof.get_connection_count(),
                "query_count": db_prof.get_query_count(),
                "slow_queries": db_prof.get_slow_query_count(),
                "average_query_time": db_prof.get_average_query_time(),
                "connection_pool_size": db_prof.get_pool_size(),
            }

            return db_metrics

        except (AttributeError, TypeError) as e:
            logger.warning("Database profiler not available: %s", str(e))
            return {
                "connection_count": 0,
                "query_count": 0,
                "slow_queries": 0,
                "average_query_time": 0.0,
                "connection_pool_size": 0,
            }
        except Exception as e:
            logger.error("Failed to get database metrics: %s", str(e))
            return {}

    async def _get_api_metrics(self) -> dict[str, Any]:
        """Get API performance metrics"""
        try:
            response_times = profiler.get_response_times()

            api_metrics = {
                "average_response_time": (sum(response_times) / len(response_times) if response_times else 0),
                "max_response_time": max(response_times) if response_times else 0,
                "min_response_time": min(response_times) if response_times else 0,
                "request_count": len(response_times),
                "error_rate": profiler.get_error_rate(),
            }

            return api_metrics

        except Exception as e:
            logger.error("Failed to get API metrics: %s", str(e))
            return {}

    async def _get_agent_metrics(self) -> dict[str, Any]:
        """Get agent performance metrics"""
        try:
            orch = _get_orchestrator()
            if orch is None:
                return {
                    "active_agents": 0,
                    "total_agents": 0,
                    "average_execution_time": 0.0,
                    "success_rate": 0.0,
                    "queue_length": 0,
                    "_default": True,
                    "degraded_reason": "orchestrator_not_available",
                }

            agent_metrics = {
                "active_agents": len(getattr(orch, "active_agents", [])),
                "total_agents": len(getattr(orch, "agent_registry", {})),
                "average_execution_time": (
                    orch.get_average_execution_time() if hasattr(orch, "get_average_execution_time") else 0.0
                ),
                "success_rate": (orch.get_success_rate() if hasattr(orch, "get_success_rate") else 0.0),
                "queue_length": (orch.get_queue_length() if hasattr(orch, "get_queue_length") else 0),
            }

            return agent_metrics

        except (AttributeError, TypeError) as e:
            logger.warning("Orchestrator not available: %s", str(e))
            return {
                "active_agents": 0,
                "total_agents": 0,
                "average_execution_time": 0.0,
                "success_rate": 0.0,
                "queue_length": 0,
                "_default": True,
                "degraded_reason": "orchestrator_unavailable",
            }
        except Exception as e:
            logger.error("Failed to get agent metrics: %s", str(e))
            return {}

    async def _identify_bottlenecks(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        """Identify performance bottlenecks"""
        bottlenecks = []

        try:
            if metrics.get("cpu", {}).get("usage_percent", 0) > self.cpu_threshold:
                bottlenecks.append(
                    {
                        "type": "cpu",
                        "severity": "high",
                        "description": f"CPU usage at {metrics['cpu']['usage_percent']:.1f}%",
                        "current_value": metrics["cpu"]["usage_percent"],
                        "threshold": self.cpu_threshold,
                    }
                )

            # Memory bottleneck
            if metrics.get("memory", {}).get("used_percent", 0) > self.memory_threshold:
                bottlenecks.append(
                    {
                        "type": "memory",
                        "severity": "high",
                        "description": f"Memory usage at {metrics['memory']['used_percent']:.1f}%",
                        "current_value": metrics["memory"]["used_percent"],
                        "threshold": self.memory_threshold,
                    }
                )

            # Database bottlenecks
            db_metrics = metrics.get("database", {})
            if db_metrics.get("slow_queries", 0) > 10:
                bottlenecks.append(
                    {
                        "type": "database",
                        "severity": "medium",
                        "description": f"High slow query count: {db_metrics['slow_queries']}",
                        "current_value": db_metrics["slow_queries"],
                        "threshold": 10,
                    }
                )

            # API bottlenecks
            api_metrics = metrics.get("api", {})
            if api_metrics.get("average_response_time", 0) > self.response_time_threshold:
                bottlenecks.append(
                    {
                        "type": "api",
                        "severity": "medium",
                        "description": f"Slow API responses: {api_metrics['average_response_time']:.2f}s",
                        "current_value": api_metrics["average_response_time"],
                        "threshold": self.response_time_threshold,
                    }
                )

            # Agent bottlenecks
            agent_metrics = metrics.get("agents", {})
            if agent_metrics.get("queue_length", 0) > 5:
                bottlenecks.append(
                    {
                        "type": "agents",
                        "severity": "low",
                        "description": f"Agent queue length: {agent_metrics['queue_length']}",
                        "current_value": agent_metrics["queue_length"],
                        "threshold": 5,
                    }
                )

        except Exception as e:
            logger.error("Failed to identify bottlenecks: %s", str(e))

        return bottlenecks

    async def _generate_recommendations(
        self, bottlenecks: list[dict[str, Any]], metrics: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate optimization recommendations based on bottlenecks and current metrics"""
        recommendations = []

        try:
            # Add general recommendations based on current metrics
            cpu_usage = metrics.get("cpu_usage", 0)
            memory_usage = metrics.get("memory_usage", 0)

            if cpu_usage > 80:
                logger.warning("High CPU usage detected: %.2f%%", cpu_usage)
            if memory_usage > 85:
                logger.warning("High memory usage detected: %.2f%%", memory_usage)

            for bottleneck in bottlenecks:
                if bottleneck["type"] == "cpu":
                    recommendations.extend(
                        [
                            {
                                "priority": "high",
                                "action": "optimize_cpu_intensive_operations",
                                "description": "Implement async processing for CPU-intensive tasks",
                                "estimated_impact": "20-30% CPU reduction",
                            },
                            {
                                "priority": "medium",
                                "action": "scale_horizontally",
                                "description": "Consider horizontal scaling to distribute load",
                                "estimated_impact": "50% load distribution",
                            },
                        ]
                    )

                elif bottleneck["type"] == "memory":
                    recommendations.extend(
                        [
                            {
                                "priority": "high",
                                "action": "implement_memory_caching",
                                "description": "Add Redis caching to reduce memory usage",
                                "estimated_impact": "30-40% memory reduction",
                            },
                            {
                                "priority": "medium",
                                "action": "optimize_data_structures",
                                "description": "Review and optimize data structures and algorithms",
                                "estimated_impact": "15-25% memory reduction",
                            },
                        ]
                    )

                elif bottleneck["type"] == "database":
                    recommendations.extend(
                        [
                            {
                                "priority": "high",
                                "action": "add_database_indexes",
                                "description": "Add indexes on frequently queried columns",
                                "estimated_impact": "50-70% query time reduction",
                            },
                            {
                                "priority": "medium",
                                "action": "optimize_queries",
                                "description": "Review and optimize slow database queries",
                                "estimated_impact": "30-50% query time reduction",
                            },
                        ]
                    )

                elif bottleneck["type"] == "api":
                    recommendations.extend(
                        [
                            {
                                "priority": "high",
                                "action": "implement_response_caching",
                                "description": "Add response caching for frequently requested data",
                                "estimated_impact": "40-60% response time reduction",
                            },
                            {
                                "priority": "medium",
                                "action": "optimize_api_endpoints",
                                "description": "Review and optimize slow API endpoints",
                                "estimated_impact": "25-40% response time reduction",
                            },
                        ]
                    )

        except Exception as e:
            logger.error("Failed to generate recommendations: %s", str(e))

        return recommendations

    def _calculate_performance_score(self, metrics: dict[str, Any]) -> float:
        """Calculate overall performance score (0-100)"""
        try:
            # Start with perfect score
            score = 100.0

            # CPU impact
            cpu_usage = metrics.get("cpu", {}).get("usage_percent", 0)
            if cpu_usage > self.cpu_threshold:
                score -= (cpu_usage - self.cpu_threshold) * 0.5

            # Memory impact
            memory_usage = metrics.get("memory", {}).get("used_percent", 0)
            if memory_usage > self.memory_threshold:
                score -= (memory_usage - self.memory_threshold) * 0.3

            # API response time impact
            avg_response_time = metrics.get("api", {}).get("average_response_time", 0)
            if avg_response_time > self.response_time_threshold:
                score -= (avg_response_time - self.response_time_threshold) * 10

            # Error rate impact
            error_rate = metrics.get("api", {}).get("error_rate", 0)
            if error_rate > self.error_rate_threshold:
                score -= (error_rate - self.error_rate_threshold) * 2

            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error("Failed to calculate performance score: %s", str(e))
            return 0.0

    def _update_performance_trends(self, metrics: dict[str, Any]) -> None:
        """Update performance trends for historical analysis"""
        try:
            timestamp = datetime.now(UTC)

            for metric_type, metric_data in metrics.items():
                if isinstance(metric_data, dict):
                    for key, value in metric_data.items():
                        if isinstance(value, (int, float)):
                            trend_key = f"{metric_type}.{key}"
                            self.performance_trends[trend_key].append({"timestamp": timestamp, "value": value})

                            # Keep only recent data (last hour)
                            cutoff = timestamp - self.baseline_period
                            self.performance_trends[trend_key] = [
                                entry for entry in self.performance_trends[trend_key] if entry["timestamp"] > cutoff
                            ]

        except Exception as e:
            logger.error("Failed to update performance trends: %s", str(e))

    async def get_performance_report(self, time_range: timedelta = timedelta(hours=1)) -> dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            analysis = await self.analyze_system_performance()

            # Get historical trends
            trends = self._analyze_trends(time_range)

            report = {
                "generated_at": datetime.now(UTC),
                "time_range": str(time_range),
                "current_analysis": analysis,
                "trends": trends,
                "summary": {
                    "overall_health": ("good" if analysis["overall_score"] > 70 else "needs_attention"),
                    "critical_issues": len([b for b in analysis["bottlenecks"] if b["severity"] == "critical"]),
                    "recommendations_count": len(analysis["recommendations"]),
                },
            }

            return report

        except Exception as e:
            logger.error("Failed to generate performance report: %s", str(e))
            return {"error": type(e).__name__}

    def _analyze_trends(self, time_range: timedelta) -> dict[str, Any]:
        """Analyze performance trends over time"""
        try:
            cutoff = datetime.now(UTC) - time_range
            trends: dict[str, Any] = {}

            for trend_key, data_points in self.performance_trends.items():
                recent_points = [p for p in data_points if p["timestamp"] > cutoff]

                if recent_points:
                    values = [p["value"] for p in recent_points]
                    trends[trend_key] = {
                        "data_points": len(recent_points),
                        "average": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "trend": self._calculate_trend(recent_points),
                    }

            return trends

        except Exception as e:
            logger.error("Failed to analyze trends: %s", str(e))
            return {}

    def _calculate_trend(self, data_points: list[dict[str, Any]]) -> str:
        """Calculate trend direction (increasing, decreasing, stable)"""
        try:
            if len(data_points) < 2:
                return "insufficient_data"

            # Simple linear trend calculation
            values = [p["value"] for p in data_points]
            n = len(values)

            # Calculate slope using simple linear regression
            x = list(range(n))
            x_mean = sum(x) / n
            y_mean = sum(values) / n

            numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values, strict=False))
            denominator = sum((xi - x_mean) ** 2 for xi in x)

            if denominator == 0:
                return "stable"

            slope = numerator / denominator

            if slope > 0.01:
                return "increasing"
            elif slope < -0.01:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error("Failed to calculate trend: %s", str(e))
            return "unknown"
