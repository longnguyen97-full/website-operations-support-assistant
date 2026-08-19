"""
Website Operations Support Assistant - Analytics Package
Module phát hiện bất thường dựa trên Luật (Rule-based) và Thống kê (Statistical):
1. statistical_detector: Z-Score, IQR Tukey Fences, Moving Average Jump.
2. rule_engine: Multi-signal evaluation (HTTP RFC 9110, DNS RFC 1035, SSL RFC 5280, Performance, DOM, Visual).
3. correlation_engine: Tương quan sự cố theo luật cứng và triệt tiêu cảnh báo trùng lặp (Noise Reduction).
4. anomaly_detector: AnomalyDetectionOrchestrator phân định rõ 2 cấu hình giám sát:
   - THRESHOLD_BASED: Cảnh báo dựa trên ngưỡng truyền thống.
   - MULTI_SIGNAL_RULE_STATISTICAL: Giám sát đa tín hiệu kết hợp Luật & Thống kê (Không sử dụng AI).
"""

from analytics.statistical_detector import ZScoreAnomalyDetector, StatisticalAnomalyDetector
from analytics.rule_engine import RuleBasedAnomalyEngine
from analytics.correlation_engine import RuleBasedCorrelationEngine
from analytics.anomaly_detector import AnomalyDetectionOrchestrator

__all__ = [
    "ZScoreAnomalyDetector",
    "StatisticalAnomalyDetector",
    "RuleBasedAnomalyEngine",
    "RuleBasedCorrelationEngine",
    "AnomalyDetectionOrchestrator"
]
