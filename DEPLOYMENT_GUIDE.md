# Robinhood Portfolio Analysis - Deployment Guide

## Overview

This guide covers deploying the Robinhood Portfolio Analysis application to production using Docker and various hosting platforms.

**Core Features**: This application includes **custom portfolio creation**, **portfolio comparison**, and **benchmark comparison** as core features. These features depend on the **stockr_backbone database** for historical stock price data, which automatically starts with the application.

## Prerequisites

- Docker and Docker Compose installed
- Git repository access
- Domain name (optional, for custom domain setup)
- SSL certificate (optional, can use Let's Encrypt)

## Quick Start with Docker Compose

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd robinhood-dashboard
```

### 2. Environment Configuration

Copy and configure environment variables:

```bash
cp env.example .env
# Edit .env with your settings
```

### 3. Local Development

```bash
# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f robinhood-dashboard

# Access application at http://localhost:8000
```

### 4. Production Deployment

```bash
# Start production environment with nginx
docker-compose -f docker-compose.prod.yml up -d

# Enable automatic backups
docker-compose -f docker-compose.backup.yml up -d
```

## Environment Variables

### Required Settings

```bash
# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-super-secret-key-here

# Database
DATABASE_URL=sqlite:///./data/portfolio.db
STOCKR_DB_PATH=./data/stockr_backbone/stockr.db

# CORS (update for your domain)
CORS_ORIGINS=https://yourdomain.com
```

### Optional Settings

```bash
# API Keys for enhanced features
ALPHA_VANTAGE_KEY=your_api_key
FINNHUB_KEY=your_api_key

# Monitoring
ENABLE_METRICS=true
METRICS_TOKEN=your_metrics_token

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log
```

## Hosting Platforms

### Railway

1. **Connect Repository**
   - Connect your GitHub repository to Railway
   - Railway will automatically detect the Dockerfile

2. **Environment Variables**
   - Set all required environment variables in Railway dashboard

3. **Database**
   - Railway provides PostgreSQL, but we're using SQLite
   - Data persists in Railway's file system

4. **Domain**
   - Use Railway's provided domain or connect custom domain
   - Enable SSL in Railway dashboard

### Render

1. **Create Web Service**
   - Connect GitHub repository
   - Select "Docker" as runtime

2. **Configure Service**
   ```yaml
   # render.yaml
   services:
     - type: web
       name: robinhood-dashboard
       env: docker
       buildCommand: docker build -t robinhood-dashboard .
       startCommand: docker run robinhood-dashboard
   ```

3. **Environment Variables**
   - Set in Render dashboard

### DigitalOcean App Platform

1. **Create App**
   - Connect GitHub repository
   - Select "Docker" as source

2. **Resource Allocation**
   - Start with Basic plan ($5/month)
   - Scale up based on usage

3. **Domain & SSL**
   - Connect custom domain
   - SSL automatically provisioned

### AWS EC2

1. **Launch EC2 Instance**
   ```bash
   # Ubuntu 22.04 LTS recommended
   # t3.micro for development, t3.small+ for production
   ```

2. **Install Docker**
   ```bash
   sudo apt update
   sudo apt install docker.io docker-compose
   sudo systemctl enable docker
   sudo systemctl start docker
   ```

3. **Deploy Application**
   ```bash
   git clone <your-repo>
   cd robinhood-dashboard
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **SSL with Let's Encrypt**
   ```bash
   sudo apt install certbot
   sudo certbot certonly --standalone -d yourdomain.com
   # Update nginx.conf with SSL paths
   ```

## Database Management

### Backup Operations

```bash
# Manual backup
docker-compose -f docker-compose.backup.yml run --rm backup-manual

# List backups
docker run --rm -v $(pwd)/backups:/app/backups robinhood-dashboard python scripts/backup.py list

# Restore backup
docker run --rm -v $(pwd)/backups:/app/backups -v $(pwd)/data:/app/data robinhood-dashboard python scripts/backup.py restore <backup-name> --confirm
```

### Data Persistence

- Databases are stored in Docker volumes
- Automatic backups run every 24 hours
- Backup retention: 30 days
- Manual backups available on demand

## Monitoring & Logging

### Health Checks

- `/health` - Comprehensive health check
- `/metrics` - Application metrics (if enabled)

### Logging

- Application logs available via Docker
- Structured logging with configurable levels
- Log rotation handled by Docker

### Monitoring Setup

```bash
# Enable metrics
ENABLE_METRICS=true
METRICS_TOKEN=your_secure_token

# Access metrics
curl -H "X-Metrics-Token: your_token" http://yourdomain.com/metrics
```

## Security Considerations

### Network Security

- All traffic routed through nginx reverse proxy
- Rate limiting configured for API endpoints
- CORS properly configured

### Application Security

- Security headers enabled
- Input validation and sanitization
- Secure file upload handling

### SSL/TLS

- HTTPS enforced in production
- HSTS headers configured
- SSL certificates automatically renewed (Let's Encrypt)

## Performance Optimization

### Container Optimization

- Multi-stage Docker build for smaller images
- Python dependencies cached in Docker layers
- Static file serving optimized

### Application Performance

- Gunicorn with Uvicorn workers for production
- Database connection pooling
- Response caching implemented
- Background task processing

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Find process using port 8000
   sudo lsof -i :8000
   # Kill process or change port in docker-compose.yml
   ```

2. **Database connection issues**
   ```bash
   # Check database file permissions
   ls -la data/
   # Ensure proper ownership
   sudo chown -R 1000:1000 data/
   ```

3. **Out of memory**
   ```bash
   # Check container logs
   docker-compose logs robinhood-dashboard
   # Increase memory allocation in hosting platform
   ```

### Logs and Debugging

```bash
# View application logs
docker-compose logs -f robinhood-dashboard

# View nginx logs
docker-compose logs -f nginx

# Enter container for debugging
docker-compose exec robinhood-dashboard bash
```

## Scaling

### Horizontal Scaling

1. **Load Balancer**
   - Use nginx or cloud load balancer
   - Multiple application instances

2. **Database**
   - Consider PostgreSQL for high traffic
   - Database connection pooling

3. **File Storage**
   - Use cloud storage (S3, Cloud Storage) for uploads
   - CDN for static assets

### Vertical Scaling

- Increase CPU/memory based on usage
- Monitor performance metrics
- Optimize database queries

## Backup & Recovery

### Automated Backups

- Daily automated backups
- 30-day retention policy
- Encrypted backup storage recommended

### Disaster Recovery

1. **Data Recovery**
   ```bash
   # Restore from backup
   python scripts/backup.py restore <backup-name> --confirm
   ```

2. **Application Recovery**
   ```bash
   # Rebuild and redeploy
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

## Cost Optimization

### Hosting Costs

- **Railway**: $5/month basic plan
- **Render**: $7/month web service
- **DigitalOcean**: $5/month App Platform
- **AWS**: ~$10/month for EC2 t3.micro

### Optimization Strategies

- Use spot instances where available
- Implement auto-scaling
- Optimize container resource usage
- Use CDN for static assets

## Support

For deployment issues:

1. Check application logs
2. Verify environment configuration
3. Test locally with Docker
4. Review hosting platform documentation
5. Check GitHub issues for similar problems

---

**Deployment completed successfully! 🚀**

Your Robinhood Portfolio Analysis application is now running in production with:
- ✅ Docker containerization
- ✅ Production server configuration
- ✅ Database persistence and backups
- ✅ Health monitoring and metrics
- ✅ Security hardening
- ✅ SSL/TLS encryption
- ✅ Comprehensive documentation
