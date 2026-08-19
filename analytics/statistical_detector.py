import math
from typing import List, Dict, Any, Tuple, Optional

class ZScoreAnomalyDetector:
    """
    Bộ phát hiện bất thường độ trễ chuỗi thời gian dựa trên thuật toán Z-Score (Standard Score):
    Z = (X - Mean) / StdDev
    
    Quy tắc phân loại mức độ theo độ lệch chuẩn:
    - |Z| < 2.5: HEALTHY (Biến thiên bình thường)
    - 2.5 <= |Z| < 3.5: WARNING (Độ trễ tăng đáng chú ý so với mức trung bình lịch sử)
    - |Z| >= 3.5: CRITICAL (Đột biến độ trễ nghiêm trọng / Latency Spike)
    """

    def __init__(
        self,
        warning_z_threshold: float = 2.5,
        critical_z_threshold: float = 3.5,
        min_samples_required: int = 5
    ):
        self.warning_z_threshold = warning_z_threshold
        self.critical_z_threshold = critical_z_threshold
        self.min_samples_required = min_samples_required

    @staticmethod
    def _calculate_mean_std(data: List[float]) -> Tuple[float, float]:
        """Tính giá trị trung bình (Mean) và độ lệch chuẩn mẫu (Standard Deviation)."""
        n = len(data)
        if n == 0:
            return 0.0, 0.0
        mean = sum(data) / n
        if n < 2:
            return mean, 0.0
        variance = sum((x - mean) ** 2 for x in data) / (n - 1)
        return mean, math.sqrt(variance)

    def analyze_latency(
        self,
        current_latency: float,
        history_latencies: List[float]
    ) -> Dict[str, Any]:
        """
        Phân tích và phát hiện bất thường độ trễ bằng Z-Score.
        """
        valid_history = [float(x) for x in history_latencies if x is not None and x >= 0]
        sample_count = len(valid_history)

        # Nếu chưa đủ mẫu lịch sử tối thiểu
        if sample_count < self.min_samples_required:
            return {
                "method": "Z_SCORE",
                "current_value_ms": round(current_latency, 2),
                "mean_ms": round(sum(valid_history) / sample_count, 2) if sample_count > 0 else round(current_latency, 2),
                "std_ms": 0.0,
                "z_score": 0.0,
                "is_anomaly": False,
                "severity": "HEALTHY",
                "sample_count": sample_count,
                "min_samples_required": self.min_samples_required,
                "reason": f"Chưa đủ dữ liệu lịch sử ({sample_count}/{self.min_samples_required} mẫu)."
            }

        mean, std = self._calculate_mean_std(valid_history)

        # Xử lý trường hợp độ lệch chuẩn = 0 (tất cả các lần trước có cùng giá trị)
        if std == 0.0:
            diff = current_latency - mean
            if diff > 500.0:
                z_score = 99.0
            else:
                z_score = 0.0
        else:
            z_score = (current_latency - mean) / std

        z_abs = abs(z_score)
        
        # Đánh giá mức độ bất thường
        if z_score >= self.critical_z_threshold:
            is_anomaly = True
            severity = "CRITICAL"
            reason = (
                f"Đột biến độ trễ nghiêm trọng (Latency Spike): Z-Score = +{round(z_score, 2)} "
                f"(Hiện tại: {round(current_latency, 2)}ms | Mean: {round(mean, 2)}ms, Std: {round(std, 2)}ms, Ngưỡng CRITICAL: Z >= {self.critical_z_threshold})."
            )
        elif z_score >= self.warning_z_threshold:
            is_anomaly = True
            severity = "WARNING"
            reason = (
                f"Độ trễ tăng cao bất thường so với lịch sử: Z-Score = +{round(z_score, 2)} "
                f"(Hiện tại: {round(current_latency, 2)}ms | Mean: {round(mean, 2)}ms, Std: {round(std, 2)}ms, Ngưỡng WARNING: Z >= {self.warning_z_threshold})."
            )
        else:
            is_anomaly = False
            severity = "HEALTHY"
            reason = f"Độ trễ ổn định trong khoảng phương sai thống kê (Z-Score = {round(z_score, 2)})."

        return {
            "method": "Z_SCORE",
            "current_value_ms": round(current_latency, 2),
            "mean_ms": round(mean, 2),
            "std_ms": round(std, 2),
            "z_score": round(z_score, 2),
            "warning_threshold": self.warning_z_threshold,
            "critical_threshold": self.critical_z_threshold,
            "is_anomaly": is_anomaly,
            "severity": severity,
            "sample_count": sample_count,
            "min_samples_required": self.min_samples_required,
            "reason": reason
        }

# Alias tương thích ngược
StatisticalAnomalyDetector = ZScoreAnomalyDetector
