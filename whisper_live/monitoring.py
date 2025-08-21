"""
Monitoring and observability module for WhisperLive
Implements metrics, logging, and tracing
"""

import os
import time
import json
import logging
import structlog
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
from contextlib import contextmanager

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Configuration
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
JAEGER_ENDPOINT = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")

# Setup structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Setup tracing
if ENABLE_TRACING:
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
    
    jaeger_exporter = JaegerExporter(
        collector_endpoint=JAEGER_ENDPOINT,
    )
    
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    LoggingInstrumentor().instrument()
else:
    tracer = None

# Prometheus metrics
if ENABLE_METRICS:
    # Counters
    transcription_requests = Counter(
        'whisper_transcription_requests_total',
        'Total number of transcription requests',
        ['status', 'model', 'language']
    )
    
    websocket_connections = Counter(
        'whisper_websocket_connections_total',
        'Total number of WebSocket connections',
        ['status']
    )
    
    errors_total = Counter(
        'whisper_errors_total',
        'Total number of errors',
        ['error_type', 'component']
    )
    
    # Histograms
    transcription_duration = Histogram(
        'whisper_transcription_duration_seconds',
        'Time spent on transcription',
        ['model', 'audio_length_bucket'],
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
    )
    
    audio_chunk_size = Histogram(
        'whisper_audio_chunk_size_bytes',
        'Size of audio chunks received',
        buckets=(1000, 5000, 10000, 50000, 100000, 500000, 1000000)
    )
    
    # Gauges
    active_connections = Gauge(
        'whisper_active_connections',
        'Number of active WebSocket connections'
    )
    
    model_memory_usage = Gauge(
        'whisper_model_memory_usage_bytes',
        'Memory usage of loaded models',
        ['model']
    )
    
    queue_size = Gauge(
        'whisper_queue_size',
        'Number of items in processing queue',
        ['queue_type']
    )
    
    cpu_usage = Gauge(
        'whisper_cpu_usage_percent',
        'CPU usage percentage'
    )
    
    gpu_usage = Gauge(
        'whisper_gpu_usage_percent',
        'GPU usage percentage',
        ['gpu_index']
    )


class MetricsCollector:
    """Collects and exposes metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.success_count = 0
        
    def record_transcription(self, duration: float, model: str, language: str = "unknown", success: bool = True):
        """Record transcription metrics"""
        if not ENABLE_METRICS:
            return
        
        status = "success" if success else "error"
        transcription_requests.labels(status=status, model=model, language=language).inc()
        
        if success:
            audio_bucket = self._get_audio_bucket(duration)
            transcription_duration.labels(model=model, audio_length_bucket=audio_bucket).observe(duration)
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.request_count += 1
    
    def record_connection(self, event: str = "connect"):
        """Record WebSocket connection events"""
        if not ENABLE_METRICS:
            return
        
        websocket_connections.labels(status=event).inc()
        
        if event == "connect":
            active_connections.inc()
        elif event == "disconnect":
            active_connections.dec()
    
    def record_error(self, error_type: str, component: str = "unknown"):
        """Record error metrics"""
        if not ENABLE_METRICS:
            return
        
        errors_total.labels(error_type=error_type, component=component).inc()
        self.error_count += 1
    
    def record_audio_chunk(self, size: int):
        """Record audio chunk size"""
        if not ENABLE_METRICS:
            return
        
        audio_chunk_size.observe(size)
    
    def update_queue_size(self, queue_type: str, size: int):
        """Update queue size gauge"""
        if not ENABLE_METRICS:
            return
        
        queue_size.labels(queue_type=queue_type).set(size)
    
    def update_resource_usage(self, cpu_percent: float, gpu_percent: Optional[float] = None, gpu_index: int = 0):
        """Update resource usage metrics"""
        if not ENABLE_METRICS:
            return
        
        cpu_usage.set(cpu_percent)
        
        if gpu_percent is not None:
            gpu_usage.labels(gpu_index=gpu_index).set(gpu_percent)
    
    def update_model_memory(self, model: str, memory_bytes: int):
        """Update model memory usage"""
        if not ENABLE_METRICS:
            return
        
        model_memory_usage.labels(model=model).set(memory_bytes)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "active_connections": active_connections._value.get() if ENABLE_METRICS else 0
        }
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format"""
        if not ENABLE_METRICS:
            return b""
        return generate_latest()
    
    @staticmethod
    def _get_audio_bucket(duration: float) -> str:
        """Determine audio duration bucket"""
        if duration < 5:
            return "0-5s"
        elif duration < 30:
            return "5-30s"
        elif duration < 60:
            return "30-60s"
        elif duration < 300:
            return "1-5m"
        else:
            return "5m+"


# Global metrics collector
metrics = MetricsCollector()


def log_performance(component: str = "unknown"):
    """Decorator to log performance metrics"""
    def decorator(f):
        @wraps(f)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await f(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    "function_executed",
                    component=component,
                    function=f.__name__,
                    duration=duration,
                    success=True
                )
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    "function_failed",
                    component=component,
                    function=f.__name__,
                    duration=duration,
                    error=str(e),
                    exc_info=True
                )
                
                metrics.record_error(error_type=type(e).__name__, component=component)
                raise
        
        @wraps(f)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = f(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    "function_executed",
                    component=component,
                    function=f.__name__,
                    duration=duration,
                    success=True
                )
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    "function_failed",
                    component=component,
                    function=f.__name__,
                    duration=duration,
                    error=str(e),
                    exc_info=True
                )
                
                metrics.record_error(error_type=type(e).__name__, component=component)
                raise
        
        if asyncio.iscoroutinefunction(f):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager for tracing spans"""
    if not ENABLE_TRACING or not tracer:
        yield
        return
    
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


class HealthCheck:
    """Health check implementation"""
    
    def __init__(self, components: Optional[Dict[str, Any]] = None):
        self.components = components or {}
        self.checks = []
    
    def add_check(self, name: str, check_func):
        """Add a health check"""
        self.checks.append((name, check_func))
    
    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks"""
        start_time = time.time()
        results = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        for name, check_func in self.checks:
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "result": result
                }
                
                if not result:
                    results["status"] = "unhealthy"
            
            except Exception as e:
                results["checks"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                results["status"] = "unhealthy"
        
        results["duration"] = time.time() - start_time
        return results
    
    def check_redis(self) -> bool:
        """Check Redis connectivity"""
        try:
            from whisper_live.auth import redis_client
            if redis_client:
                redis_client.ping()
                return True
            return False
        except:
            return False
    
    def check_model(self) -> bool:
        """Check if model is loaded"""
        # This should check if the Whisper model is loaded
        # Implementation depends on your model management
        return True
    
    def check_disk_space(self, min_gb: float = 1.0) -> bool:
        """Check available disk space"""
        import shutil
        stat = shutil.disk_usage("/")
        available_gb = stat.free / (1024 ** 3)
        return available_gb >= min_gb


# Global health checker
health = HealthCheck()
health.add_check("redis", health.check_redis)
health.add_check("model", health.check_model)
health.add_check("disk", health.check_disk_space)

import asyncio