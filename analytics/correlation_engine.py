"""
Directed Acyclic Graph (DAG) Incident Correlation Engine:
Mô hình đồ thị có hướng không chu trình xử lý Đa Lỗi, Đa Tín Hiệu (Multi-Fault, Multi-Signal Causal Graph).

Mô hình hóa chuỗi phụ thuộc hạ tầng mạng Internet:
  [DNS Resolver (RFC 1035)]
          │
          ▼
   [TCP / Socket L4]
     │          │
     ▼          ▼
[SSL/TLS L6]  [Plain HTTP]
     │          │
     └────┬─────┘
          ▼
 [HTTP Gateway / Reverse Proxy L7] ──► [SRE Latency / SLAs]
          │
          ▼
 [Backend App / Database]
          │
          ▼
  [DOM Structure (W3C)]
          │
          ▼
[Visual UI / Pixel Diff]

Đặc tính:
1. Phát hiện ĐA LỖI ĐỘC LẬP (Multi-Root-Cause): Không bỏ sót các sự cố độc lập xảy ra đồng thời.
2. Khử nhiễu lan truyền (Cascading Noise Reduction): Triệt tiêu các lỗi con phát sinh từ nút cha.
3. Sinh biểu đồ Mermaid trực quan hóa trạng thái nút (Root Cause, Cascading, Healthy).
"""

from typing import List, Dict, Any, Optional, Set, Tuple


class DAGNode:
    """Đại diện cho một nút trong đồ thị nhân quả hạ tầng."""
    def __init__(self, node_id: str, label: str, layer: str, rfc_standard: str = ""):
        self.node_id = node_id
        self.label = label
        self.layer = layer
        self.rfc_standard = rfc_standard
        self.violations: List[Dict[str, Any]] = []
        self.is_root_cause: bool = False
        self.is_cascading: bool = False
        self.status: str = "HEALTHY"  # HEALTHY, ROOT_CAUSE, CASCADING, WARNING

    @property
    def has_fault(self) -> bool:
        return len(self.violations) > 0


class DAGCorrelationEngine:
    """
    Bộ tương quan sự cố bằng Đồ thị DAG (Directed Acyclic Graph).
    Xử lý đa lỗi, đa tín hiệu và cô lập lỗi lan truyền theo cấu trúc phân tầng mạng.
    """

    # Danh sách các nút chuẩn trong hạ tầng dịch vụ web
    NODES_DEF = [
        {"id": "DNS", "label": "🌐 Phân Giải DNS", "layer": "L3/L7 Naming", "rfc": "RFC 1035"},
        {"id": "TCP_SOCKET", "label": "🔌 Kết Nối TCP / Port", "layer": "L4 Transport", "rfc": "RFC 793"},
        {"id": "SSL_TLS", "label": "🔒 Chứng Chỉ SSL/TLS", "layer": "L6 Security", "rfc": "RFC 5280 / 8446"},
        {"id": "HTTP_GATEWAY", "label": "🚪 Cổng HTTP / Proxy", "layer": "L7 Application", "rfc": "RFC 9110"},
        {"id": "APP_BACKEND", "label": "⚙️ Ứng Dụng Backend", "layer": "L7 App/Database", "rfc": "Internal App"},
        {"id": "PERF_LATENCY", "label": "⏱️ Độ Trễ & Hiệu Năng", "layer": "SRE Golden Signals", "rfc": "Google SRE"},
        {"id": "DOM_STRUCTURE", "label": "📄 Cấu Trúc DOM HTML", "layer": "W3C Document", "rfc": "W3C DOM Spec"},
        {"id": "VISUAL_UI", "label": "👁️ Trực Quan Giao Diện", "layer": "User Experience", "rfc": "Pixel Rendering"},
    ]

    # Các cạnh phụ thuộc có hướng: (Parent -> Child)
    # Lỗi ở Parent sẽ lan truyền gây hỏng hóc hoặc biến dạng ở Child
    DEPENDENCY_EDGES = [
        ("DNS", "TCP_SOCKET", "Không có IP thì không mở được Socket TCP"),
        ("TCP_SOCKET", "SSL_TLS", "Không có kết nối L4 thì không thể bắt tay TLS"),
        ("TCP_SOCKET", "HTTP_GATEWAY", "Lỗi socket/port làm đứt gãy kết nối HTTP"),
        ("SSL_TLS", "HTTP_GATEWAY", "Lỗi chứng chỉ SSL ngăn cản phiên HTTPS hoàn tất"),
        ("HTTP_GATEWAY", "APP_BACKEND", "Gateway chuyển tiếp yêu cầu tới ứng dụng nội bộ"),
        ("HTTP_GATEWAY", "PERF_LATENCY", "Gateway nghẽn làm tăng thời gian phản hồi"),
        ("APP_BACKEND", "PERF_LATENCY", "Backend xử lý chậm gây trễ toàn trình"),
        ("APP_BACKEND", "DOM_STRUCTURE", "Backend sập hoặc lỗi 500 làm thiếu hụt HTML DOM"),
        ("DOM_STRUCTURE", "VISUAL_UI", "DOM vỡ hoặc trống rỗng làm biến dạng giao diện UI"),
    ]

    # Bảng ánh xạ Rule ID sang DAG Node ID
    RULE_TO_NODE_MAP = {
        # Tầng DNS
        "DNS_RESOLUTION_FAILED": "DNS",
        "DNS_BASELINE_MISMATCH": "DNS",
        "DNS_UNEXPECTED_DRIFT": "DNS",
        "DNS_NO_RECORDS": "DNS",
        "DNS_HIGH_LATENCY": "DNS",

        # Tầng TCP / Socket
        "TCP_CONNECTION_REFUSED": "TCP_SOCKET",
        "TCP_PORT_CLOSED": "TCP_SOCKET",

        # Tầng SSL/TLS
        "SSL_CERTIFICATE_EXPIRED": "SSL_TLS",
        "SSL_HOSTNAME_MISMATCH": "SSL_TLS",
        "SSL_UNTRUSTED_CA": "SSL_TLS",
        "SSL_CLOSE_TO_EXPIRY": "SSL_TLS",
        "SSL_EXPIRING_SOON": "SSL_TLS",
        "SSL_INVALID_UNKNOWN": "SSL_TLS",
        "SSL_SELF_SIGNED": "SSL_TLS",
        "SSL_HANDSHAKE_ERROR": "SSL_TLS",

        # Tầng HTTP Gateway / Proxy
        "HTTP_REDIRECT_LOOP_DETECTED": "HTTP_GATEWAY",
        "HTTP_EXCESSIVE_REDIRECTS": "HTTP_GATEWAY",
        "HTTP_CONN_FAILED": "HTTP_GATEWAY",
        "HTTP_TIMEOUT_ERROR": "HTTP_GATEWAY",
        "HTTP_502_BAD_GATEWAY": "HTTP_GATEWAY",
        "HTTP_504_GATEWAY_TIMEOUT": "HTTP_GATEWAY",
        "HTTP_STATUS_MISMATCH": "HTTP_GATEWAY",
        "HTTP_4XX_CLIENT_ERROR": "HTTP_GATEWAY",

        # Tầng Backend App
        "HTTP_500_INTERNAL_ERROR": "APP_BACKEND",
        "HTTP_503_SERVICE_UNAVAILABLE": "APP_BACKEND",
        "HTTP_5XX_SERVER_DOWN": "APP_BACKEND",
        "HTTP_5XX_SERVER_ERROR": "APP_BACKEND",

        # Tầng Hiệu năng & Thống kê
        "PERF_CRITICAL_LATENCY": "PERF_LATENCY",
        "PERF_DEGRADED_LATENCY": "PERF_LATENCY",
        "STAT_Z_SCORE_SPIKE": "PERF_LATENCY",
        "PERF_TTFB_ANOMALY": "PERF_LATENCY",

        # Tầng Cấu trúc DOM
        "DOM_STRUCTURAL_CORRUPTION": "DOM_STRUCTURE",
        "DOM_MISSING_BODY": "DOM_STRUCTURE",
        "DOM_MISSING_HEAD": "DOM_STRUCTURE",
        "DOM_CONTENT_EMPTY": "DOM_STRUCTURE",
        "DOM_CRITICAL_ELEMENT_MISSING": "DOM_STRUCTURE",

        # Tầng Giao diện Trực quan
        "VISUAL_REGRESSION_DETECTED": "VISUAL_UI",
        "VISUAL_BLANK_PAGE": "VISUAL_UI",
        "VISUAL_LAYOUT_SHIFT": "VISUAL_UI",
    }

    # Các lỗi ở nút cha mang tính chất đứt gãy tuyệt đối (Blocking Upstream Failure)
    # khiến mọi lỗi ở các nút con bên dưới đều bị coi là Cascading Fault
    BLOCKING_FAILURE_RULES = {
        "DNS": {"DNS_RESOLUTION_FAILED", "DNS_NO_RECORDS"},
        "TCP_SOCKET": {"TCP_CONNECTION_REFUSED", "TCP_PORT_CLOSED"},
        "SSL_TLS": {"SSL_CERTIFICATE_EXPIRED", "SSL_HOSTNAME_MISMATCH", "SSL_UNTRUSTED_CA"},
        "HTTP_GATEWAY": {"HTTP_REDIRECT_LOOP_DETECTED", "HTTP_CONN_FAILED", "HTTP_TIMEOUT_ERROR", "HTTP_502_BAD_GATEWAY"},
        "APP_BACKEND": {"HTTP_500_INTERNAL_ERROR", "HTTP_5XX_SERVER_DOWN", "HTTP_503_SERVICE_UNAVAILABLE"},
        "DOM_STRUCTURE": {"DOM_STRUCTURAL_CORRUPTION", "DOM_MISSING_BODY"}
    }

    # Ma trận quan hệ nhân quả (Causal Consequence Matrix):
    # Xác định chính xác lỗi nào ở nút con là hệ quả trực tiếp từ nút cha
    CAUSAL_CONSEQUENCES = {
        "DNS": {
            "TCP_SOCKET": {"TCP_CONNECTION_REFUSED", "TCP_PORT_CLOSED", "HTTP_CONN_FAILED"},
            "HTTP_GATEWAY": {"HTTP_CONN_FAILED", "HTTP_TIMEOUT_ERROR"},
            "DOM_STRUCTURE": {"DOM_STRUCTURAL_CORRUPTION", "DOM_MISSING_BODY", "DOM_CONTENT_EMPTY"},
            "VISUAL_UI": {"VISUAL_REGRESSION_DETECTED", "VISUAL_BLANK_PAGE"}
        },
        "TCP_SOCKET": {
            "SSL_TLS": {"SSL_HANDSHAKE_ERROR"},
            "HTTP_GATEWAY": {"HTTP_CONN_FAILED", "HTTP_TIMEOUT_ERROR"},
            "DOM_STRUCTURE": {"DOM_STRUCTURAL_CORRUPTION", "DOM_MISSING_BODY", "DOM_CONTENT_EMPTY"},
            "VISUAL_UI": {"VISUAL_REGRESSION_DETECTED", "VISUAL_BLANK_PAGE"}
        },
        "SSL_TLS": {
            "HTTP_GATEWAY": {"HTTP_CONN_FAILED", "SSL_HANDSHAKE_ERROR"},
            "DOM_STRUCTURE": {"DOM_STRUCTURAL_CORRUPTION", "DOM_MISSING_BODY", "DOM_CONTENT_EMPTY"},
            "VISUAL_UI": {"VISUAL_REGRESSION_DETECTED", "VISUAL_BLANK_PAGE"}
        },
        "HTTP_GATEWAY": {
            "APP_BACKEND": {"HTTP_502_BAD_GATEWAY", "HTTP_504_GATEWAY_TIMEOUT"},
            "DOM_STRUCTURE": {"DOM_STRUCTURAL_CORRUPTION", "DOM_MISSING_BODY", "DOM_CONTENT_EMPTY"},
            "VISUAL_UI": {"VISUAL_REGRESSION_DETECTED", "VISUAL_BLANK_PAGE"}
        },
        "APP_BACKEND": {
            "DOM_STRUCTURE": {"DOM_STRUCTURAL_CORRUPTION", "DOM_MISSING_BODY", "DOM_CONTENT_EMPTY"},
            "VISUAL_UI": {"VISUAL_REGRESSION_DETECTED", "VISUAL_BLANK_PAGE"},
            "PERF_LATENCY": {"PERF_CRITICAL_LATENCY", "PERF_DEGRADED_LATENCY", "STAT_Z_SCORE_SPIKE"}
        },
        "DOM_STRUCTURE": {
            "VISUAL_UI": {"VISUAL_REGRESSION_DETECTED", "VISUAL_BLANK_PAGE", "VISUAL_LAYOUT_SHIFT"}
        }
    }

    def __init__(self):
        # Xây dựng cấu trúc danh sách kề (Adjacency List)
        self.adj: Dict[str, List[Tuple[str, str]]] = {n["id"]: [] for n in self.NODES_DEF}
        self.reverse_adj: Dict[str, List[Tuple[str, str]]] = {n["id"]: [] for n in self.NODES_DEF}
        for u, v, reason in self.DEPENDENCY_EDGES:
            self.adj[u].append((v, reason))
            self.reverse_adj[v].append((u, reason))

    def _get_all_ancestors(self, node_id: str) -> Set[str]:
        """Tìm toàn bộ các nút tổ tiên (Ancestors) của một nút trong DAG."""
        ancestors = set()
        queue = [node_id]
        while queue:
            curr = queue.pop(0)
            for parent, _ in self.reverse_adj.get(curr, []):
                if parent not in ancestors:
                    ancestors.add(parent)
                    queue.append(parent)
        return ancestors

    def correlate_violations(self, violations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Thực hiện tương quan đa lỗi bằng thuật toán DAG Causal Traversal:
        - Phân bổ các vi phạm vào các nút đồ thị.
        - Phân định các Root Causes độc lập (Multi-Root-Cause) vs Cascading Faults lan truyền.
        - Triệt tiêu các cảnh báo hệ quả (Noise Reduction).
        - Sinh mã biểu đồ Mermaid DAG trực quan.
        """
        if not violations:
            return {
                "has_incident": False,
                "incident_type": "NO_INCIDENT",
                "root_cause_summary": "Hệ thống hoạt động bình thường, tất cả các nút hạ tầng trong trạng thái Healthy.",
                "overall_severity": "HEALTHY",
                "suppressed_alerts_count": 0,
                "primary_issue": None,
                "correlated_signals": [],
                "dag_analysis": {
                    "is_multi_fault": False,
                    "root_causes": [],
                    "cascading_faults": [],
                    "nodes_status": {n["id"]: "HEALTHY" for n in self.NODES_DEF},
                    "mermaid_diagram": self._generate_mermaid_code({}, [], [])
                }
            }

        # Khởi tạo các Node DAG
        nodes_dict: Dict[str, DAGNode] = {
            n["id"]: DAGNode(n["id"], n["label"], n["layer"], n["rfc"])
            for n in self.NODES_DEF
        }

        # 1. Ánh xạ các vi phạm vào Node tương ứng
        unmapped_violations = []
        for v in violations:
            rule_id = v.get("rule_id", "")
            signal = v.get("signal", "")

            # Phân loại tinh vi nếu là HTTP_CONN_FAILED có thể do Socket refused
            target_node_id = self.RULE_TO_NODE_MAP.get(rule_id)
            if not target_node_id:
                # Phân loại fallback theo signal
                if signal == "DNS":
                    target_node_id = "DNS"
                elif signal == "SSL":
                    target_node_id = "SSL_TLS"
                elif signal == "PERFORMANCE" or signal == "Z_SCORE_STATISTICAL":
                    target_node_id = "PERF_LATENCY"
                elif signal == "DOM":
                    target_node_id = "DOM_STRUCTURE"
                elif signal == "VISUAL":
                    target_node_id = "VISUAL_UI"
                else:
                    target_node_id = "HTTP_GATEWAY"

            # Đặc biệt: Nếu HTTP_CONN_FAILED nhưng mô tả chứa 'refused' hoặc '10061' -> Gán TCP_SOCKET
            desc_lower = str(v.get("description", "")).lower()
            if rule_id == "HTTP_CONN_FAILED" and ("refused" in desc_lower or "10061" in desc_lower):
                target_node_id = "TCP_SOCKET"

            if target_node_id in nodes_dict:
                nodes_dict[target_node_id].violations.append(v)
            else:
                unmapped_violations.append(v)

        # 2. Xác định các nút có lỗi (Failing Nodes)
        failing_node_ids = {node_id for node_id, node in nodes_dict.items() if node.has_fault}

        # 3. Phân định Root Cause vs Cascading Fault dựa trên Causal Ancestors
        root_cause_nodes: List[DAGNode] = []
        cascading_nodes: List[Tuple[DAGNode, str]] = []  # (Node, Cause Reason)
        suppressed_violations: List[Dict[str, Any]] = []

        for node_id in failing_node_ids:
            curr_node = nodes_dict[node_id]
            ancestors = self._get_all_ancestors(node_id)
            
            # Kiểm tra xem lỗi ở nút hiện tại có phải là hệ quả nhân quả (Causal Consequence) từ một ancestor bị lỗi
            cascading_trigger_parent = None
            curr_rules = {v.get("rule_id") for v in curr_node.violations}
            for parent_id in ancestors:
                if parent_id in failing_node_ids:
                    parent_node = nodes_dict[parent_id]
                    parent_rules = {v.get("rule_id") for v in parent_node.violations}
                    blocking_rules = self.BLOCKING_FAILURE_RULES.get(parent_id, set())

                    # Kiểm tra xem cha có lỗi blocking VÀ lỗi ở nút con có nằm trong tập hệ quả do cha gây ra
                    consequence_rules = self.CAUSAL_CONSEQUENCES.get(parent_id, {}).get(node_id, set())
                    if (parent_rules & blocking_rules) and (curr_rules & consequence_rules):
                        cascading_trigger_parent = parent_node
                        break

            if cascading_trigger_parent:
                # Đây là lỗi lan truyền do nút cha gây ra
                curr_node.is_cascading = True
                curr_node.status = "CASCADING"
                reason = f"Lỗi thứ cấp lan truyền từ nút gốc: '{cascading_trigger_parent.label}'"
                cascading_nodes.append((curr_node, reason))
                suppressed_violations.extend(curr_node.violations)
            else:
                # Đây là một nguyên nhân gốc độc lập!
                curr_node.is_root_cause = True
                has_critical = any(v.get("severity") == "CRITICAL" for v in curr_node.violations)
                curr_node.status = "ROOT_CAUSE" if has_critical else "WARNING"
                root_cause_nodes.append(curr_node)

        # Trường hợp ngoại lệ: Nếu toàn bộ nút đều bị đánh dấu cascading (vòng lặp giả lập), chọn nút cao nhất làm root cause
        if not root_cause_nodes and failing_node_ids:
            # Chọn nút có bậc tổ tiên ít nhất
            sorted_by_ancestor_count = sorted(
                [nodes_dict[nid] for nid in failing_node_ids],
                key=lambda n: len(self._get_all_ancestors(n.node_id))
            )
            fallback_root = sorted_by_ancestor_count[0]
            fallback_root.is_root_cause = True
            fallback_root.is_cascading = False
            fallback_root.status = "ROOT_CAUSE"
            root_cause_nodes.append(fallback_root)
            # Loại bỏ khỏi cascading list
            cascading_nodes = [cn for cn in cascading_nodes if cn[0].node_id != fallback_root.node_id]
            suppressed_violations = [v for v in suppressed_violations if v not in fallback_root.violations]

        # 4. Xác định mức độ nghiêm trọng chung (Overall Severity)
        severities = {v["severity"] for v in violations}
        overall_severity = "CRITICAL" if "CRITICAL" in severities else ("WARNING" if "WARNING" in severities else "HEALTHY")

        # 5. Phân loại sự cố chính và tóm tắt đa nguyên nhân (Multi-Root-Cause Summary)
        is_multi_fault = len(root_cause_nodes) > 1
        
        # Chọn primary issue từ Root Cause Node đầu tiên
        primary_issue = None
        if root_cause_nodes:
            primary_issue = root_cause_nodes[0].violations[0]
        elif violations:
            primary_issue = violations[0]

        # Tổng hợp tóm tắt nguyên nhân gốc
        rc_summaries = []
        for rc_node in root_cause_nodes:
            top_v = rc_node.violations[0]
            rc_summaries.append(f"[{rc_node.label}]: {top_v.get('title')} ({top_v.get('description')})")

        if is_multi_fault:
            incident_type = "MULTI_FAULT_INCIDENT"
            root_cause_summary = f"Phát hiện {len(root_cause_nodes)} sự cố độc lập đồng thời (Multi-Root-Cause): " + " | ".join(rc_summaries)
        elif root_cause_nodes:
            top_v = root_cause_nodes[0].violations[0]
            incident_type = top_v.get("rule_id", "SINGLE_FAULT_INCIDENT")
            root_cause_summary = f"{top_v.get('title')}: {top_v.get('description')}"
        else:
            incident_type = "GENERAL_ANOMALY"
            root_cause_summary = primary_issue.get("description") if primary_issue else "Phát hiện bất thường."

        # 6. Sinh cấu trúc Mermaid Diagram
        nodes_status_map = {n["id"]: nodes_dict[n["id"]].status for n in self.NODES_DEF}
        mermaid_code = self._generate_mermaid_code(nodes_status_map, root_cause_nodes, cascading_nodes)

        # 7. Danh sách chi tiết các Root Causes và Cascading Faults
        formatted_root_causes = []
        for rcn in root_cause_nodes:
            formatted_root_causes.append({
                "node_id": rcn.node_id,
                "label": rcn.label,
                "layer": rcn.layer,
                "rfc_standard": rcn.rfc_standard,
                "violations_count": len(rcn.violations),
                "primary_violation": rcn.violations[0],
                "all_violations": rcn.violations
            })

        formatted_cascading_faults = []
        for cn, reason in cascading_nodes:
            formatted_cascading_faults.append({
                "node_id": cn.node_id,
                "label": cn.label,
                "layer": cn.layer,
                "reason": reason,
                "suppressed_violations_count": len(cn.violations),
                "suppressed_violations": cn.violations
            })

        return {
            "has_incident": True,
            "incident_type": incident_type,
            "root_cause_summary": root_cause_summary,
            "overall_severity": overall_severity,
            "primary_issue": primary_issue,
            "raw_violations_count": len(violations),
            "suppressed_alerts_count": len(suppressed_violations),
            "correlated_signals": list({v.get("signal", "UNKNOWN") for v in violations}),
            "all_violations": violations,
            "dag_analysis": {
                "is_multi_fault": is_multi_fault,
                "root_causes_count": len(root_cause_nodes),
                "cascading_faults_count": len(cascading_nodes),
                "root_causes": formatted_root_causes,
                "cascading_faults": formatted_cascading_faults,
                "nodes_status": nodes_status_map,
                "mermaid_diagram": mermaid_code
            }
        }

    def _generate_mermaid_code(
        self,
        nodes_status: Dict[str, str],
        root_causes: List[DAGNode],
        cascading_nodes: List[Tuple[DAGNode, str]]
    ) -> str:
        """Sinh mã biểu đồ Mermaid (Directional Graph) chuẩn định dạng."""
        lines = [
            "graph TD",
            "  %% PHÂN TẦNG HẠ TẦNG MẠNG & ỨNG DỤNG WEB",
            "  subgraph Infra [🌐 Tầng Hạ Tầng Mạng & Kết Nối L3-L6]",
            "    DNS[\"🌐 Phân Giải DNS (RFC 1035)\"]",
            "    TCP_SOCKET[\"🔌 Kết Nối TCP / Port (L4)\"]",
            "    SSL_TLS[\"🔒 Chứng Chỉ SSL/TLS (RFC 5280)\"]",
            "  end",
            "  subgraph Service [🚪 Tầng Dịch Vụ & Ứng Dụng L7]",
            "    HTTP_GATEWAY[\"🚪 Cổng HTTP / Nginx (RFC 9110)\"]",
            "    APP_BACKEND[\"⚙️ Ứng Dụng Backend & DB\"]",
            "    PERF_LATENCY[\"⏱️ Độ Trễ & SLAs (Golden Signals)\"]",
            "  end",
            "  subgraph Presentation [👁️ Tầng Trình Diễn & Trải Nghiệm]",
            "    DOM_STRUCTURE[\"📄 Cấu Trúc DOM (W3C HTML)\"]",
            "    VISUAL_UI[\"👁️ Trực Quan UI (Playwright)\"]",
            "  end",
            "",
            "  %% CÁC CẠNH ĐỊNH HƯỚNG NHÂN QUẢ (Causal Edges)",
            "  DNS -->|Resolve IP| TCP_SOCKET",
            "  TCP_SOCKET -->|TLS Handshake| SSL_TLS",
            "  SSL_TLS -->|HTTPS Session| HTTP_GATEWAY",
            "  TCP_SOCKET -.->|Plain HTTP| HTTP_GATEWAY",
            "  HTTP_GATEWAY -->|Reverse Proxy| APP_BACKEND",
            "  APP_BACKEND -->|Render Response| DOM_STRUCTURE",
            "  DOM_STRUCTURE -->|Render Pixels| VISUAL_UI",
            "  HTTP_GATEWAY -->|Gateway Latency| PERF_LATENCY",
            "  APP_BACKEND -->|Execution Time| PERF_LATENCY",
            "",
            "  %% PHONG CÁCH MÀU SẮC TRỰC QUAN (SRE Status Classes)",
            "  classDef healthy fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5,font-weight:bold;",
            "  classDef rootCause fill:#7f1d1d,stroke:#ef4444,stroke-width:3px,color:#fee2e2,font-weight:bold;",
            "  classDef cascading fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#fef3c7,stroke-dasharray: 5 5;",
            "  classDef warning fill:#713f12,stroke:#eab308,stroke-width:2px,color:#fef9c3,font-weight:bold;"
        ]

        # Áp dụng class cho từng node
        for nid in [n["id"] for n in self.NODES_DEF]:
            st = nodes_status.get(nid, "HEALTHY")
            if st == "ROOT_CAUSE":
                lines.append(f"  class {nid} rootCause;")
            elif st == "CASCADING":
                lines.append(f"  class {nid} cascading;")
            elif st == "WARNING":
                lines.append(f"  class {nid} warning;")
            else:
                lines.append(f"  class {nid} healthy;")

        return "\n".join(lines)


# Lớp tương thích ngược (Backward Compatibility Alias)
class RuleBasedCorrelationEngine(DAGCorrelationEngine):
    """
    Alias kế thừa DAGCorrelationEngine để tương thích 100% với các mã nguồn gọi cũ.
    """
    pass
