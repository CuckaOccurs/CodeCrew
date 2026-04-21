#!/bin/bash
# CodeCrew Cache Mop - Automated cleanup for CachyOS
# Threshold: 1GB

THRESHOLD_KB=1048576 # 1GB in KB
CACHE_DIR="$HOME/.cache"

# Calculate size of cache directory
CURRENT_SIZE=$(du -sk "$CACHE_DIR" | cut -f1)

if [ "$CURRENT_SIZE" -gt "$THRESHOLD_KB" ]; then
    echo "--- [MOP] Cache exceeding 1GB ($CURRENT_SIZE KB). Cleaning... ---"
    
    # 1. Clear Pacman cache (keep last 2)
    sudo paccache -r
    
    # 2. Clear thumbnail cache
    rm -rf ~/.cache/thumbnails/*
    
    # 3. Clear temporary files older than 7 days
    find ~/.cache -type f -atime +7 -delete
    
    # Final check
    NEW_SIZE=$(du -sk "$CACHE_DIR" | cut -f1)
    echo "--- [MOP] Cleanup complete. New size: $NEW_SIZE KB ---"
else
    echo "--- [MOP] Cache size ($CURRENT_SIZE KB) is within limits. No action needed. ---"
fi
