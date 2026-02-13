#!/usr/bin/env bash
# deploy-ue5.sh — Package UE5 project and deploy to runtime directory
# Called by Jenkinsfile during the "UE5 Package & Deploy" stage.
#
# Usage:
#   ./deploy/deploy-ue5.sh [--skip-package]
#
# Environment variables (set by Jenkinsfile):
#   UE5_ENGINE_DIR   — UE5 engine root (default: /opt/UnrealEngine)
#   UE5_PROJECT_DIR  — UE5 project source (default: /home/adamlyu/VirtualStudio)
#   UE5_DEPLOY_DIR   — Runtime deploy target (default: /opt/virtual-studio)
#   UE5_SERVICE_NAME — systemd service name (default: virtual-studio)

set -euo pipefail

UE5_ENGINE_DIR="${UE5_ENGINE_DIR:-/opt/UnrealEngine}"
UE5_PROJECT_DIR="${UE5_PROJECT_DIR:-/home/adamlyu/VirtualStudio}"
UE5_DEPLOY_DIR="${UE5_DEPLOY_DIR:-/opt/virtual-studio}"
UE5_SERVICE_NAME="${UE5_SERVICE_NAME:-virtual-studio}"
ARCHIVE_DIR="${UE5_DEPLOY_DIR}_staging"
BACKUP_DIR="${UE5_DEPLOY_DIR}_backup"

SKIP_PACKAGE=false
if [[ "${1:-}" == "--skip-package" ]]; then
    SKIP_PACKAGE=true
fi

echo "=== UE5 Deploy Script ==="
echo "Engine:  ${UE5_ENGINE_DIR}"
echo "Project: ${UE5_PROJECT_DIR}"
echo "Deploy:  ${UE5_DEPLOY_DIR}"
echo "Service: ${UE5_SERVICE_NAME}"
echo "Skip package: ${SKIP_PACKAGE}"
echo ""

# ---- 1. Validate prerequisites ----
if [[ ! -f "${UE5_PROJECT_DIR}/VirtualStudio.uproject" ]]; then
    echo "ERROR: UE5 project not found at ${UE5_PROJECT_DIR}/VirtualStudio.uproject"
    exit 1
fi

if [[ "${SKIP_PACKAGE}" == "false" ]] && [[ ! -f "${UE5_ENGINE_DIR}/Engine/Build/BatchFiles/RunUAT.sh" ]]; then
    echo "ERROR: UE5 engine not found at ${UE5_ENGINE_DIR}"
    exit 1
fi

# ---- 2. Package UE5 project (Linux Shipping) ----
if [[ "${SKIP_PACKAGE}" == "false" ]]; then
    echo ">>> Packaging UE5 project..."
    rm -rf "${ARCHIVE_DIR}"

    "${UE5_ENGINE_DIR}/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun \
        -project="${UE5_PROJECT_DIR}/VirtualStudio.uproject" \
        -platform=Linux \
        -configuration=Shipping \
        -cook -stage -pak -archive \
        -archivedirectory="${ARCHIVE_DIR}" \
        -nocompileuat \
        -unattended \
        -utf8output

    if [[ ! -d "${ARCHIVE_DIR}/LinuxNoEditor" ]]; then
        echo "ERROR: Packaging failed — expected output not found"
        exit 1
    fi
    echo ">>> Packaging complete."
else
    echo ">>> Skipping package step."
    if [[ ! -d "${ARCHIVE_DIR}/LinuxNoEditor" ]]; then
        echo "ERROR: No staged build found at ${ARCHIVE_DIR}/LinuxNoEditor"
        echo "       Run without --skip-package first."
        exit 1
    fi
fi

# ---- 3. Stop UE5 service ----
echo ">>> Stopping ${UE5_SERVICE_NAME} service..."
sudo systemctl stop "${UE5_SERVICE_NAME}" 2>/dev/null || true
sleep 3

# ---- 4. Backup current deployment ----
if [[ -d "${UE5_DEPLOY_DIR}" ]]; then
    echo ">>> Backing up current deployment to ${BACKUP_DIR}..."
    rm -rf "${BACKUP_DIR}"
    mv "${UE5_DEPLOY_DIR}" "${BACKUP_DIR}"
fi

# ---- 5. Deploy new build ----
echo ">>> Deploying new build..."
mkdir -p "${UE5_DEPLOY_DIR}"
cp -a "${ARCHIVE_DIR}/LinuxNoEditor/." "${UE5_DEPLOY_DIR}/"
chmod +x "${UE5_DEPLOY_DIR}/VirtualStudio.sh" 2>/dev/null || true

# ---- 6. Install / update systemd service ----
if [[ -f "deploy/virtual-studio.service" ]]; then
    echo ">>> Updating systemd service file..."
    sudo cp deploy/virtual-studio.service /etc/systemd/system/"${UE5_SERVICE_NAME}.service"
    sudo systemctl daemon-reload
fi

# ---- 7. Start UE5 service ----
echo ">>> Starting ${UE5_SERVICE_NAME} service..."
sudo systemctl start "${UE5_SERVICE_NAME}"
sleep 5

# ---- 8. Health check ----
echo ">>> Health check..."
MAX_WAIT=60
ELAPSED=0
while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    if curl -sf http://localhost:30010/api/v1/preset > /dev/null 2>&1; then
        echo ">>> UE5 Remote Control API is responding!"
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo "    Waiting for UE5 to start... (${ELAPSED}s / ${MAX_WAIT}s)"
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo "WARNING: UE5 health check timed out after ${MAX_WAIT}s."
    echo "         Check logs: sudo journalctl -u ${UE5_SERVICE_NAME} -f"
    # Don't fail the build — UE5 may just need more time to init
fi

# ---- 9. Verify Pixel Streaming ----
if curl -sf http://localhost:80 > /dev/null 2>&1; then
    echo ">>> Pixel Streaming signalling server is responding!"
else
    echo "WARNING: Pixel Streaming not responding on :80"
    echo "         You may need to start the signalling server separately."
fi

echo ""
echo "=== UE5 Deploy Complete ==="
echo "Service status: $(systemctl is-active ${UE5_SERVICE_NAME} 2>/dev/null || echo 'unknown')"
echo "Remote Control: http://localhost:30010"
echo "Pixel Streaming: http://localhost:80"
