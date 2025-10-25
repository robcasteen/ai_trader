"""
Error tracking system for monitoring component health and errors.
"""
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque


class ErrorTracker:
    """Track errors across all bot components."""
    
    def __init__(self, max_errors: int = 100, log_file: Optional[Path] = None):
        """
        Initialize error tracker.
        
        Args:
            max_errors: Maximum number of errors to keep in memory
            log_file: Optional path to persist errors to disk
        """
        self.max_errors = max_errors
        self.log_file = log_file
        self.errors = deque(maxlen=max_errors)
        self.error_counts = {}  # Component -> error count in last 24h
        
        # Load existing errors from disk if available
        if log_file and log_file.exists():
            self._load_from_disk()
    
    def log_error(
        self,
        component: str,
        message: str,
        error: Optional[Exception] = None,
        severity: str = "error",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an error from a component.
        
        Args:
            component: Component name (e.g., "openai", "kraken", "rss")
            message: Error message
            error: Optional exception object
            severity: Error severity (error, warning, critical)
            metadata: Additional context (API endpoint, request ID, etc.)
        """
        error_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "message": message,
            "severity": severity,
            "metadata": metadata or {},
        }
        
        # Add stack trace if exception provided
        if error:
            error_entry["exception"] = str(error)
            error_entry["exception_type"] = type(error).__name__
            error_entry["stack_trace"] = traceback.format_exc()
        
        # Add to memory
        self.errors.append(error_entry)
        
        # Update error count for component
        if component not in self.error_counts:
            self.error_counts[component] = 0
        self.error_counts[component] += 1
        
        # Persist to disk if enabled
        if self.log_file:
            self._save_to_disk()
        
        # Also log to standard logger
        logging.error(f"[{component.upper()}] {message}", exc_info=error)
    
    def get_errors(
        self,
        component: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent errors, optionally filtered.
        
        Args:
            component: Filter by component name
            severity: Filter by severity level
            limit: Maximum number of errors to return
        
        Returns:
            List of error entries (newest first)
        """
        errors = list(self.errors)
        
        # Filter by component
        if component:
            errors = [e for e in errors if e["component"] == component]
        
        # Filter by severity
        if severity:
            errors = [e for e in errors if e["severity"] == severity]
        
        # Return newest first
        errors.reverse()
        
        return errors[:limit]
    
    def get_component_errors(self, component: str) -> List[Dict[str, Any]]:
        """Get all errors for a specific component."""
        return self.get_errors(component=component)
    
    def get_error_count(self, component: str) -> int:
        """Get error count for a component in last 24h."""
        return self.error_counts.get(component, 0)
    
    def get_last_error(self, component: str) -> Optional[Dict[str, Any]]:
        """Get most recent error for a component."""
        component_errors = self.get_component_errors(component)
        return component_errors[0] if component_errors else None
    
    def clear_errors(self, component: Optional[str] = None) -> int:
        """
        Clear errors, optionally for a specific component.
        
        Args:
            component: If provided, only clear errors for this component
        
        Returns:
            Number of errors cleared
        """
        if component:
            # Clear errors for specific component
            original_count = len(self.errors)
            self.errors = deque(
                [e for e in self.errors if e["component"] != component],
                maxlen=self.max_errors
            )
            cleared = original_count - len(self.errors)
            
            # Reset error count
            if component in self.error_counts:
                self.error_counts[component] = 0
        else:
            # Clear all errors
            cleared = len(self.errors)
            self.errors.clear()
            self.error_counts.clear()
        
        # Persist to disk
        if self.log_file:
            self._save_to_disk()
        
        return cleared
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get health summary for all components.
        
        Returns:
            Dict with component names as keys and health info as values
        """
        components = set(e["component"] for e in self.errors)
        
        summary = {}
        for component in components:
            last_error = self.get_last_error(component)
            error_count = self.get_error_count(component)
            
            summary[component] = {
                "error_count": error_count,
                "last_error": last_error,
                "status": "error" if error_count > 0 else "operational"
            }
        
        return summary
    
    def _save_to_disk(self) -> None:
        """Persist errors to disk."""
        try:
            if not self.log_file:
                return
            
            data = {
                "errors": list(self.errors),
                "error_counts": self.error_counts,
            }
            
            with open(self.log_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save errors to disk: {e}")
    
    def _load_from_disk(self) -> None:
        """Load errors from disk."""
        try:
            if not self.log_file or not self.log_file.exists():
                return
            
            with open(self.log_file, "r") as f:
                data = json.load(f)
            
            self.errors = deque(data.get("errors", []), maxlen=self.max_errors)
            self.error_counts = data.get("error_counts", {})
        except Exception as e:
            logging.error(f"Failed to load errors from disk: {e}")


# Global error tracker instance
error_tracker = ErrorTracker(
    max_errors=100,
    log_file=Path(__file__).parent / "logs" / "errors.json"
)
