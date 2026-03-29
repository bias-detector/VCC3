#!/bin/bash

# VCC 3 - GCP VM Cleanup Script
# Tears down the GCP VM and associated resources

set -e

PROJECT_ID="${1:-}"
VM_NAME="${2:-vcc-3-backend}"
ZONE="${3:-us-central1-a}"

if [[ -z "$PROJECT_ID" ]]; then
    echo "Usage: ./cleanup-gcp-vm.sh <PROJECT_ID> [VM_NAME] [ZONE]"
    echo "Example: ./cleanup-gcp-vm.sh my-gcp-project vcc-3-backend us-central1-a"
    exit 1
fi

echo "======================================"
echo "VCC 3 - GCP VM Cleanup"
echo "======================================"
echo "Project: $PROJECT_ID"
echo "VM Name: $VM_NAME"
echo "Zone: $ZONE"
echo "======================================"
echo ""
echo "WARNING: This will delete the VM and firewall rules."
read -p "Continue? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo "Cancelled."
    exit 0
fi

# Set project
gcloud config set project "$PROJECT_ID"

# Delete VM
echo "Deleting VM instance..."
gcloud compute instances delete "$VM_NAME" --zone "$ZONE" --quiet

# Delete firewall rule
echo "Deleting firewall rule..."
FIREWALL_RULE="vcc-3-allow-8000"
if gcloud compute firewall-rules describe "$FIREWALL_RULE" &>/dev/null; then
    gcloud compute firewall-rules delete "$FIREWALL_RULE" --quiet
fi

echo ""
echo "======================================"
echo "Cleanup Complete!"
echo "======================================"
