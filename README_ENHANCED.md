# 🎙️ WhisperLive-NubemAI

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-green)](https://www.docker.com/)
[![Security](https://img.shields.io/badge/Security-Enhanced-orange)](AUDIT_REPORT.md)

**Production-ready real-time audio transcription service** powered by OpenAI's Whisper model with enterprise-grade features.

## 🚀 Features

### Core Capabilities
- ⚡ **Real-time transcription** via WebSocket
- 🔄 **REST API** for batch processing
- 🌍 **Multi-language support** (100+ languages)
- 🎯 **Multiple backends**: Faster-Whisper, TensorRT, OpenVINO
- 📱 **Cross-platform**: Browser, iOS, Android support

### Enterprise Features
- 🔐 **JWT Authentication** with role-based access
- 🛡️ **Rate limiting** and DDoS protection
- 📊 **Prometheus metrics** and Grafana dashboards
- 🔍 **Distributed tracing** with Jaeger
- 💾 **Redis caching** for improved performance
- 🐘 **PostgreSQL** for user management
- 🔄 **Auto-scaling** and load balancing
- 🚦 **Health checks** and monitoring
- 📝 **Structured logging** with JSON format
- 🔒 **SSL/TLS support** for secure connections

## 📋 Prerequisites

- Python 3.9+
- Docker & Docker Compose
- NVIDIA GPU (optional, for acceleration)
- Redis 7+
- PostgreSQL 16+
- 4GB+ RAM minimum
- 10GB+ disk space

## 🛠️ Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/NUbem000/WhisperLive-NubemAI.git
cd WhisperLive-NubemAI

# Copy environment configuration
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Docker Deployment (Recommended)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f whisper-server
```

### 3. Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/server-updated.txt

# Run enhanced server
python -m whisper_live.server_enhanced
```

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Server
SERVER_PORT=9090
MAX_CLIENTS=10
BACKEND=faster_whisper

# Security
ENABLE_AUTH=true
JWT_SECRET=your-secret-key
API_KEY=your-api-key

# Model
WHISPER_MODEL=base
USE_GPU=true

# Database
DATABASE_URL=postgresql://user:pass@localhost/whisper_live

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Monitoring
ENABLE_METRICS=true
LOG_LEVEL=INFO
```

### Available Whisper Models

| Model | Size | RAM | Accuracy | Speed |
|-------|------|-----|----------|-------|
| tiny | 39M | ~1GB | ★★☆☆☆ | ★★★★★ |
| base | 74M | ~1GB | ★★★☆☆ | ★★★★☆ |
| small | 244M | ~2GB | ★★★★☆ | ★★★☆☆ |
| medium | 769M | ~5GB | ★★★★★ | ★★☆☆☆ |
| large | 1550M | ~10GB | ★★★★★ | ★☆☆☆☆ |

## 📡 API Usage

### Authentication

```bash
# Get JWT token
curl -X POST http://localhost:9090/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1Q...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### REST API Transcription

```bash
# Transcribe audio file
curl -X POST http://localhost:9090/transcribe \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_data": "base64_encoded_audio",
    "language": "en",
    "model": "base"
  }'
```

### WebSocket Streaming

```javascript
// JavaScript client example
const ws = new WebSocket('ws://localhost:9090/ws/transcribe');

ws.onopen = () => {
  // Send authentication
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'YOUR_JWT_TOKEN'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'transcription') {
    console.log('Transcribed:', data.text);
  }
};

// Send audio chunks
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    // Process and send audio chunks to WebSocket
  });
```

### Python Client

```python
import asyncio
import websockets
import json

async def transcribe():
    uri = "ws://localhost:9090/ws/transcribe"
    
    async with websockets.connect(
        uri,
        extra_headers={"Authorization": f"Bearer {token}"}
    ) as websocket:
        
        # Send audio data
        await websocket.send(audio_bytes)
        
        # Receive transcription
        response = await websocket.recv()
        data = json.loads(response)
        print(f"Transcription: {data['text']}")

asyncio.run(transcribe())
```

## 📊 Monitoring

### Metrics Endpoint

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# Health check
curl http://localhost:9090/health

# Server statistics
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:9090/stats
```

### Grafana Dashboard

Access Grafana at `http://localhost:3000` (default: admin/admin)

Pre-configured dashboards:
- Server Overview
- Transcription Performance
- Resource Usage
- Error Tracking

### Jaeger Tracing

Access Jaeger UI at `http://localhost:16686`

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=whisper_live --cov-report=html

# Run specific test suite
python -m pytest tests/test_enhanced.py -v

# Performance tests
python -m pytest tests/test_enhanced.py::TestPerformance -v

# Security tests
python -m pytest tests/test_enhanced.py::TestSecurity -v
```

## 🚀 Production Deployment

### AWS/GCP Deployment

```bash
# Build production image
docker build -f docker/Dockerfile.production -t whisper-live:prod .

# Push to registry
docker tag whisper-live:prod gcr.io/your-project/whisper-live:latest
docker push gcr.io/your-project/whisper-live:latest

# Deploy with Kubernetes
kubectl apply -f k8s/deployment.yaml
```

### Performance Optimization

1. **GPU Acceleration**: Use NVIDIA GPUs with CUDA 12.2+
2. **Model Quantization**: Enable 8-bit quantization
3. **Caching**: Configure Redis with sufficient memory
4. **Load Balancing**: Use multiple server instances
5. **CDN**: Serve static assets via CDN

### Security Best Practices

1. ✅ Always use HTTPS/WSS in production
2. ✅ Rotate JWT secrets regularly
3. ✅ Enable rate limiting
4. ✅ Use strong passwords
5. ✅ Keep dependencies updated
6. ✅ Monitor security alerts
7. ✅ Implement RBAC
8. ✅ Use secrets management (Vault/KMS)

## 📈 Benchmarks

| Metric | Value | Conditions |
|--------|-------|------------|
| Latency | <2s | Base model, GPU |
| Throughput | 100 req/s | 8 CPU cores |
| Accuracy | >95% | Clean audio |
| Concurrent Users | 100+ | With load balancing |
| Memory Usage | ~2GB | Per instance |

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- Original [WhisperLive](https://github.com/collabora/WhisperLive) by Collabora
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)

## 📞 Support

- 📧 Email: support@nubem.ai
- 💬 Discord: [Join our server](https://discord.gg/nubem)
- 🐛 Issues: [GitHub Issues](https://github.com/NUbem000/WhisperLive-NubemAI/issues)
- 📚 Docs: [Documentation](https://docs.nubem.ai/whisperlive)

## 🗺️ Roadmap

- [ ] Multi-GPU support
- [ ] Speaker diarization
- [ ] Real-time translation
- [ ] Mobile SDKs
- [ ] Kubernetes Helm charts
- [ ] Serverless deployment
- [ ] WebRTC integration
- [ ] Fine-tuning interface

---

Built with ❤️ by NubemAI Team