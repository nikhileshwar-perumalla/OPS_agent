import random
import time
import numpy as np
from datetime import datetime

class MetricsGenerator:
    def __init__(self):
        self.baseline_cpu = 30.0
        self.baseline_memory = 40.0
        self.baseline_latency = 0.05  # seconds
        self.status = "healthy"
        self._anomaly_mode = None
        self._start_time = None

    def generate_baseline(self):
        """Pure baseline generation"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": round(max(0, min(100, self.baseline_cpu + random.uniform(-5, 5))), 2),
            "memory_percent": round(max(0, min(100, self.baseline_memory + random.uniform(-2, 2))), 2),
            "disk_percent": round(max(0, min(100, 45.0 + random.uniform(-1, 1))), 2), # New Metric
            "latency_seconds": round(max(0, self.baseline_latency + random.uniform(-0.01, 0.01)), 4),
            "anomaly_active": None
        }

    def tick(self, active_incidents):
        """
        Calculates metrics based on active incidents (stateless).
        """
        metrics = self.generate_baseline()
        anomalies = []
        
        # Apply effects of each incident (Additive/Max logic)
        for incident in active_incidents:
            itype = str(incident.type.value) if hasattr(incident.type, 'value') else str(incident.type)
            anomalies.append(itype)
            
            if itype == 'high_cpu':
                # Maximize CPU
                metrics['cpu_percent'] = max(metrics['cpu_percent'], round(95 + random.uniform(-2, 3), 2))
                
            elif itype == 'memory_leak':
                # Maximize Memory
                metrics['memory_percent'] = max(metrics['memory_percent'], round(96 + random.uniform(-1, 2), 2))
                if metrics['memory_percent'] > 99: metrics['memory_percent'] = 99
                
            elif itype == 'network_latency':
                # Maximize Latency
                metrics['latency_seconds'] = max(metrics['latency_seconds'], round(2.5 + random.uniform(0.1, 0.5), 4))
                
            elif itype == 'service_down':
                # Service down overrides High CPU (if down, no cpu usage?) or maybe keeps it high if thrashing?
                # Let's say it zeroes out CPU/Latency as requests fail fast?
                # Actually, usually 503s are fast.
                metrics['cpu_percent'] = 0.5 # Idle
                metrics['latency_seconds'] = 0.01
                
            elif itype == 'disk_usage_high':
                metrics['disk_percent'] = max(getattr(metrics, 'disk_percent', 0), round(95 + random.uniform(-1, 2), 2))

            elif itype == 'process_crash':
                metrics['latency_seconds'] = max(metrics['latency_seconds'], 2.0)

            elif itype == 'database_lock':
                metrics['latency_seconds'] = max(metrics['latency_seconds'], round(5.0 + random.uniform(0.5, 1.5), 4))
                
            elif itype == 'ssl_expiry':
                pass # No metric effect
                
        metrics['anomaly_active'] = ",".join(anomalies) if anomalies else None
        return metrics

    # Deprecated methods
    def set_anomaly(self, anomaly_type): pass
    def clear_anomaly(self): pass
    def generate_metrics(self): return self.generate_baseline()
