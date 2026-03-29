#!/bin/bash

# VCC 3 - GCP VM Deployment Script
# Creates a Google Cloud VM and deploys the VCC 3 backend service

set -e

PROJECT_ID="${1:-}"
VM_NAME="${2:-vcc-3-backend}"
ZONE="${3:-us-central1-a}"
MACHINE_TYPE="${4:-e2-medium}"
IMAGE_FAMILY="debian-12"
IMAGE_PROJECT="debian-cloud"

if [[ -z "$PROJECT_ID" ]]; then
    echo "Usage: ./deploy-gcp-vm.sh <PROJECT_ID> [VM_NAME] [ZONE] [MACHINE_TYPE]"
    echo "Example: ./deploy-gcp-vm.sh my-gcp-project vcc-3-backend us-central1-a e2-medium"
    echo ""
    echo "Available machine types: e2-small, e2-medium, e2-standard-2, e2-standard-4"
    exit 1
fi

echo "======================================"
echo "VCC 3 - GCP VM Deployment"
echo "======================================"
echo "Project: $PROJECT_ID"
echo "VM Name: $VM_NAME"
echo "Zone: $ZONE"
echo "Machine Type: $MACHINE_TYPE"
echo "======================================"

# Check if gcloud CLI is installed
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

# Set project
echo "[1/5] Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# Check if VM already exists
if gcloud compute instances describe "$VM_NAME" --zone "$ZONE" &>/dev/null; then
    echo "[2/5] VM '$VM_NAME' already exists. Skipping creation."
    VM_CREATED=false
else
    echo "[2/5] Creating GCP VM instance..."
    gcloud compute instances create "$VM_NAME" \
        --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" \
        --image-family="$IMAGE_FAMILY" \
        --image-project="$IMAGE_PROJECT" \
        --boot-disk-size=30GB \
        --enable-display-device=false \
        --maintenance-policy=MIGRATE \
        --provisioning-model=STANDARD \
        --scopes=compute-rw,storage-ro,service-management,service-control,logging.write,monitoring.write,pubsub,cloud-platform \
        --tags=vcc-3,http-server,https-server
    
    VM_CREATED=true
    echo "VM created successfully."
fi

# Get VM external IP
echo "[3/5] Retrieving VM IP address..."
EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" --zone "$ZONE" --format='value(networkInterfaces[0].accessConfigs[0].natIP)')
if [[ -z "$EXTERNAL_IP" ]]; then
    echo "WARNING: Could not retrieve external IP. VM may still be starting up."
    EXTERNAL_IP="<PENDING>"
fi
echo "VM External IP: $EXTERNAL_IP"

# Create firewall rule for port 8000
echo "[4/5] Ensuring firewall rule for port 8000..."
FIREWALL_RULE="vcc-3-allow-8000"
if gcloud compute firewall-rules describe "$FIREWALL_RULE" &>/dev/null; then
    echo "Firewall rule already exists."
else
    gcloud compute firewall-rules create "$FIREWALL_RULE" \
        --allow=tcp:8000 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=vcc-3 \
        --description="Allow port 8000 for VCC 3 backend"
    echo "Firewall rule created."
fi

# Deploy code and start service
echo "[5/5] Deploying VCC 3 backend to VM..."
gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --command='
        set -e
        
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo bash get-docker.sh
        rm get-docker.sh
        
        echo "Starting Docker service..."
        sudo systemctl start docker
        sudo systemctl enable docker
        
        echo "Cloning VCC 3 repository..."
        if [ ! -d vcc-3 ]; then
            git clone https://github.com/YOUR_USERNAME/VCC.git vcc-3
        fi
        cd vcc-3
        
        echo "Building Docker image..."
        docker build -t vcc-3-backend .
        
        echo "Running VCC 3 backend service..."
        docker run -d \
            --name vcc-3-backend \
            -p 8000:8000 \
            -e SERVICE_NAME="VCC-3 Cloud VM" \
            -e OLLAMA_URL="http://ollama:11434" \
            -e OLLAMA_MODEL="llama3.2:1b" \
            -e OLLAMA_TIMEOUT_SECONDS="20" \
            -e MAX_LOCAL_CONCURRENCY="8" \
            -e MAX_LOCAL_QUEUE="50" \
            -e PUBLIC_BASE_URL="http://'"$EXTERNAL_IP"':8000" \
            vcc-3-backend
        
        echo "Service deployed successfully!"
        echo "API Health: curl http://localhost:8000/api/health"
        echo "Frontend: http://'"$EXTERNAL_IP"':8000"
    '

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
if [[ "$EXTERNAL_IP" != "<PENDING>" ]]; then
    echo "➜ Frontend:  http://$EXTERNAL_IP:8000"
    echo "➜ API:       http://$EXTERNAL_IP:8000/api"
    echo ""
    echo "SSH into VM: gcloud compute ssh $VM_NAME --zone $ZONE"
    echo "View logs:   gcloud compute instances get-serial-port-output $VM_NAME --zone $ZONE"
else
    echo "➜ IP is still being assigned. Check again in a few seconds."
    echo "   gcloud compute instances describe $VM_NAME --zone $ZONE --format='value(networkInterfaces[0].accessConfigs[0].natIP)'"
fi
echo ""
echo "To connect local VM to this cloud backend, set in local .env:"
echo "CLOUD_BACKEND_URL=http://$EXTERNAL_IP:8000"
echo "======================================"
