# AWS Deployment Guide — CryptoBot AI Dashboard

## Option 1: AWS EC2 (Recommended for full control)

### 1. Launch EC2 Instance
- AMI: Amazon Linux 2023 or Ubuntu 22.04
- Instance: t3.small (2 vCPU, 2GB RAM) — sufficient
- Security Group: Open port 8080 (or 80/443 with nginx)

### 2. Connect & Install
```bash
ssh -i your-key.pem ec2-user@<your-ec2-ip>

# Install Docker
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 3. Deploy
```bash
# Clone/upload your project
git clone <your-repo> crypto_trading_system
cd crypto_trading_system

# Set environment variables
export BYBIT_API_KEY="your_key"
export BYBIT_API_SECRET="your_secret"

# Launch
docker-compose up -d

# View logs
docker-compose logs -f dashboard
```

### 4. Access
Open `http://<your-ec2-ip>:8080` in your browser.

---

## Option 2: AWS App Runner (Easiest)

1. Push code to GitHub/ECR
2. Go to AWS App Runner console
3. Create service → Source: Container registry or GitHub
4. Set port: 8080
5. Add env vars: BYBIT_API_KEY, BYBIT_API_SECRET, STARTING_BALANCE
6. Deploy

---

## Option 3: AWS ECS Fargate (Serverless containers)

### 1. Push to ECR
```bash
aws ecr create-repository --repository-name cryptobot-dashboard
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

docker build -t cryptobot-dashboard .
docker tag cryptobot-dashboard:latest <account>.dkr.ecr.<region>.amazonaws.com/cryptobot-dashboard:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/cryptobot-dashboard:latest
```

### 2. Create ECS Task Definition
- Container image: your ECR URI
- Port: 8080
- CPU: 512, Memory: 1024
- Environment variables: BYBIT_API_KEY, BYBIT_API_SECRET

### 3. Create ECS Service
- Launch type: FARGATE
- Desired count: 1
- Load balancer: Application LB (for HTTPS)

---

## Quick Local Test (Before deploying)
```bash
# Without Docker
pip install flask gunicorn
python dashboard/app.py

# With Docker
docker build -t cryptobot-dashboard .
docker run -p 8080:8080 -v ./logs:/app/logs cryptobot-dashboard
```

## Adding HTTPS (Production)
Use nginx reverse proxy or AWS ALB with ACM certificate:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
