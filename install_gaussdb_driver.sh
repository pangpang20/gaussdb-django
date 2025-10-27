#!/bin/bash
# install_gaussdb_driver.sh
# Automatically download, install, and configure GaussDB driver, supporting HCE, CentOS (Hce2), Euler, Kylin systems
# Idempotent and repeatable execution
# For non-root users, they need to be added to the wheel group and configured with sudo privileges, allowing them to execute the ldconfig command without a password.

set -euo pipefail

#===================
#     Basic Configuration     
#===================
DOWNLOAD_URL="https://dbs-download.obs.cn-north-1.myhuaweicloud.com/GaussDB/1730887196055/GaussDB_driver.zip"
HOME_DIR="$HOME"
ZIP_FILE="$HOME_DIR/GaussDB_driver.zip"
DRIVER_DIR="$HOME_DIR/GaussDB_driver/Centralized"
LIB_DIR="$HOME_DIR/GaussDB_driver_lib"
LOG_FILE="/tmp/gaussdb_driver_install_$(date +%Y%m%d_%H%M%S).log"

#===================
#     Utility Functions     
#===================
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

cleanup() {
    log "Cleaning up temporary files..."
    [[ -f "$ZIP_FILE" ]] && rm -rf "$ZIP_FILE" 2>/dev/null
    [[ -d "$HOME_DIR/GaussDB_driver" ]] && rm -rf "$HOME_DIR/GaussDB_driver" 2>/dev/null
}

#===================
#     Parameter Checks     
#===================
command -v wget >/dev/null || { log "Error: wget is missing"; exit 1; }
command -v unzip >/dev/null || { log "Error: unzip is missing"; exit 1; }
command -v tar >/dev/null || { log "Error: tar is missing"; exit 1; }

log "Starting GaussDB driver installation..."

#===================
#     Download and Extract   
#===================
if [[ ! -f "$ZIP_FILE" ]]; then
    log "Downloading driver file..."
    wget -O "$ZIP_FILE" "$DOWNLOAD_URL" >> "$LOG_FILE" 2>&1 || { log "Error: Download failed"; exit 1; }
else
    log "Driver file already exists, skipping download"
fi

log "Extracting driver file..."
unzip -o "$ZIP_FILE" -d "$HOME_DIR/" >> "$LOG_FILE" 2>&1 || { log "Error: Extraction failed"; exit 1; }


#===================
#     Detect System and Architecture   
#===================
ARCH=$(uname -m)
case "$ARCH" in
    x86_64) ARCH_TYPE="X86_64" ;;
    aarch64) ARCH_TYPE="arm_64" ;;
    *) log "Error: Unsupported architecture: $ARCH"; exit 1 ;;
esac
log "architecture: $ARCH_TYPE"
OS_TYPE=""
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    case "$ID" in
        centos|hce)
            if [[ -d "$DRIVER_DIR/Hce2_$ARCH_TYPE" ]]; then
                OS_TYPE="Hce2_$ARCH_TYPE"
            fi
            ;;
        euler)
            VERSION=$(grep -oP 'VERSION_ID="\K[^"]+' /etc/os-release)
            case "$VERSION" in
                2.5*)
                    if [[ -d "$DRIVER_DIR/Euler2.5_$ARCH_TYPE" ]]; then
                        OS_TYPE="Euler2.5_$ARCH_TYPE"
                    fi
                    ;;
                2.9*)
                    if [[ -d "$DRIVER_DIR/Euler2.9_$ARCH_TYPE" ]]; then
                        OS_TYPE="Euler2.9_$ARCH_TYPE"
                    fi
                    ;;
            esac
            ;;
        kylin)
            if [[ -d "$DRIVER_DIR/Kylinv10_$ARCH_TYPE" ]]; then
                OS_TYPE="Kylinv10_$ARCH_TYPE"
            fi
            ;;
        *)
            log "Error: Unsupported operating system: $ID"; exit 1
            ;;
    esac
else
    log "Warning: Unable to read /etc/os-release, attempting to infer system type from directory structure"
    if [[ -d "$DRIVER_DIR/Hce2_$ARCH_TYPE" ]]; then
        OS_TYPE="Hce2_$ARCH_TYPE"
    elif [[ -d "$DRIVER_DIR/Euler2.5_$ARCH_TYPE" ]]; then
        OS_TYPE="Euler2.5_$ARCH_TYPE"
    elif [[ -d "$DRIVER_DIR/Euler2.9_$ARCH_TYPE" ]]; then
        OS_TYPE="Euler2.9_$ARCH_TYPE"
    elif [[ -d "$DRIVER_DIR/Kylinv10_$ARCH_TYPE" ]]; then
        OS_TYPE="Kylinv10_$ARCH_TYPE"
    else
        log "Error: Unsupported operating system or architecture: $ARCH_TYPE"; exit 1
    fi
fi
log "Detected system: $OS_TYPE"
if [[ -z "$OS_TYPE" ]]; then
    log "Error: No matching driver directory found: $DRIVER_DIR/*_$ARCH_TYPE"; exit 1
fi



#===================
#     Copy Driver Package   
#===================
mkdir -p "$LIB_DIR"
DRIVER_PACKAGE=$(find "$DRIVER_DIR/$OS_TYPE" -name "*Python.tar.gz" | head -n 1)
if [[ -z "$DRIVER_PACKAGE" ]]; then
    log "Error: No driver package found for $OS_TYPE"; exit 1
fi

log "Copying driver package: $DRIVER_PACKAGE to $LIB_DIR"
log "$DRIVER_PACKAGE" "$LIB_DIR/"
cp "$DRIVER_PACKAGE" "$LIB_DIR/"

#===================
#     Extract Driver Package   
#===================
log "Extracting driver package to $LIB_DIR..."
tar --no-same-owner -zxvf "$LIB_DIR/$(basename "$DRIVER_PACKAGE")" -C "$LIB_DIR/" >> "$LOG_FILE" 2>&1 || { log "Error: Failed to extract driver package"; exit 1; }
rm -f "$LIB_DIR/$(basename "$DRIVER_PACKAGE")"
chmod 755 -R "$LIB_DIR"

#===================
#     Configure Dynamic Link Library   
#===================
log "Configuring user-level dynamic link library path..."
LIB_DIR="$HOME_DIR/GaussDB_driver_lib"

if ! grep -q "$LIB_DIR/lib" "$HOME/.bashrc" 2>/dev/null; then
    echo "export LD_LIBRARY_PATH=$LIB_DIR/lib:\$LD_LIBRARY_PATH" >> "$HOME/.bashrc"
    log "Added LD_LIBRARY_PATH to ~/.bashrc"
fi

sudo bash -c "echo \"$LIB_DIR/lib\" > /etc/ld.so.conf.d/$(whoami).conf"
log "Added $LIB_DIR/lib to /etc/ld.so.conf.d/$(whoami).conf"

sudo ldconfig
log "Updated ldconfig cache"

#===================
#     Verify Installation     
#===================
if ls "$LIB_DIR/lib" 2>/dev/null | grep -q libpq; then
	cleanup
    log "============================================================="
    log "GaussDB driver installed successfully (user mode)!"
    log "Dynamic link library configured: $LIB_DIR/lib"
    log "Log file: $LOG_FILE"
    log "============================================================="
else
    log "Error: libpq not found in $LIB_DIR/lib"
    exit 1
fi

#===================
#     Reload Environment (only if sourced)
#===================
if [[ "$0" != "$BASH_SOURCE" ]]; then
    log "Reloading ~/.bashrc so LD_LIBRARY_PATH takes effect..."
    source ~/.bashrc
    log "Environment reloaded successfully."
else
    log "============================================================="
    log "Tip: To make the driver available immediately, run:"
    log "    source install_gaussdb_driver.sh"
    log "or manually execute: source ~/.bashrc"
    log "============================================================="
fi