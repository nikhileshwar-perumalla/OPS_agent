import os
import time

class LogSource:
    def fetch_new_logs(self) -> list:
        raise NotImplementedError

class FileLogSource(LogSource):
    def __init__(self, file_path):
        self.file_path = file_path
        self.last_position = 0
        # Ensure file exists
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write("")
                
    def fetch_new_logs(self) -> list:
        if not os.path.exists(self.file_path):
            return []
            
        logs = []
        try:
            with open(self.file_path, 'r') as f:
                f.seek(self.last_position)
                lines = f.readlines()
                self.last_position = f.tell()
                
                for line in lines:
                    logs.append(line.strip())
        except Exception as e:
            print(f"[LogSource Error] {e}")
            
        return logs

class ObservationWindow:
    def __init__(self, window_size=10):
        self.window_size = window_size
        self.logs = []
        
    def add_logs(self, new_logs: list):
        self.logs.extend(new_logs)
        # Keep only recent logs? Or is window based on ticks?
        # Assuming tick-based, we might just store everything for now or truncate
        # For this phase, let's keep last N logs for feature extraction
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]
            
    def get_features(self):
        """
        Extract features for the Agent.
        """
        error_count = sum(1 for log in self.logs if "ERROR" in log or "CRITICAL" in log)
        total = len(self.logs)
        error_rate = (error_count / total) if total > 0 else 0.0
        
        return {
            "log_volume": total,
            "error_rate": round(error_rate, 2),
            "recent_errors": error_count,
            "log_samples": [log for log in self.logs if "ERROR" in log or "CRITICAL" in log][-3:] # Last 3 errors
        }
