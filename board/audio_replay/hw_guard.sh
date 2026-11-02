#!/bin/bash
# Guard against the failure that hung the board on 2026-11-02:
# shengdi-product.service owns the FPGA while it runs. Opening a second PYNQ session from this account
# (/dev/mem, overlay download) while the service is active contends for the same device and can wedge
# the PS. Every hardware script must therefore refuse to touch the hardware while the service is active.
#
# Usage:  source this file at the top of any board script that talks to the FPGA.
#         hardware_allowed  -> returns 0 when it is safe to touch the FPGA, 1 otherwise.

SERVICE=shengdi-product.service

service_active() {
    systemctl is-active --quiet "$SERVICE" 2>/dev/null
}

hardware_allowed() {
    if service_active; then
        echo "HW_GUARD_REFUSED: $SERVICE is active and owns the FPGA." >&2
        echo "HW_GUARD_HINT: stop it first (sudo systemctl stop $SERVICE) or use the product's own CLI." >&2
        return 1
    fi
    return 0
}

# For scripts that are legitimately read-only, this prints a one line verdict instead of refusing.
hardware_status() {
    if service_active; then
        echo "HW_GUARD service_active=1 hardware_access=forbidden file_reading=allowed"
    else
        echo "HW_GUARD service_active=0 hardware_access=allowed"
    fi
}
