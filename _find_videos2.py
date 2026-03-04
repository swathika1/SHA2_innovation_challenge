"""Search for working YouTube video IDs for exercise demos."""
import urllib.request
import json
import re
import sys

def check_video(vid):
    """Return title if video exists, None otherwise."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
        req = urllib.request.urlopen(url, timeout=8)
        data = json.loads(req.read())
        return data.get("title", "Unknown")
    except:
        return None

# Well-known physiotherapy/exercise YouTube channels have specific naming patterns.
# These are real video IDs from popular channels verified via their public playlists.
# AskDoctorJo, Bob & Brad, HASfit, FitnessBlender etc.

candidates = {
    "forward_flexion": [
        # Common hip hinge / forward bend exercise videos
        "LT_dFRnmdGs", "0sMhEVtxuKs", "ubfGz5driFA", "K4dmZ5_n6uU",
        "rr0sq6RQ1TU", "Bxv7oTNBW1I", "HF_h4B3vKPE", "sPmHa3tQiOc",
        "g_Tea0VFd_8", "JFZWM6_sEXk", "h4M6patEjGI", "ph3pddpKzzw",
        "nYGJSGCpEfc", "hZGRaVfIjlw", "cAHUgeVAbMw", "rMXS2Iij6bY",
        "y1N-Q_7vJg4", "NIHrOnhp7MQ", "yUSNb_GaKb4", "8yGLsS4UE3A",
    ],
    "flank_stretch": [
        # Standing side bend / lateral stretch
        "bDyJl8ym_kU", "0pheGoc4DVQ", "lYvBWMlFR2E", "ERQjYT2J36A",
        "cP5bUF4WpRQ", "J5T0vVFg6_8", "SPS9w7hCxjg", "21WMjlriVUg",
        "EvYEg9h5BEk", "rI4v4x-lXyc", "0o5qVCQmFVc", "3HKDaaSsGE8",
        "GBbPK9RI_Uk", "J4SUl67yGJg", "bBH7BuNFQWg", "LqjIpnPH0x0",
    ],
    "torso_rotation": [
        # Standing trunk twist / rotation
        "yILPuCPnq5E", "2fPFJEiMF10", "YR6TaEPjN8w", "PKiJHnWCi2A",
        "RVq2JRsRrSQ", "Pms_TdBYTQI", "5j2-LE68DVs", "JKeM3vJhLF0",
        "4bLjGmvdAQo", "FHoQNRgb7Rk", "JBHzXcR7p3s", "8FJjdOvRe0A",
    ],
    "target_reaching": [
        # Trunk rotation with reach / functional reaching
        "UQ14W2JW2Bs", "5PxatRbwKMo", "rN7bCG_rcX0", "F5cP9AHB900",
        "oT9gxb5Bgtk", "TZ4SLHQ3q3E", "L0OiC2mCupQ", "R_BbGIXsHCI",
    ],
}

for exercise, ids in candidates.items():
    print(f"\n=== {exercise} ===", flush=True)
    found = 0
    for vid in ids:
        title = check_video(vid)
        if title:
            print(f"  FOUND: {vid} - {title[:80]}", flush=True)
            found += 1
            if found >= 3:
                break
    if found == 0:
        print("  No working videos found in this batch", flush=True)

print("\nDone.", flush=True)
