"""Temporary script to find working YouTube video IDs for exercise demos."""
import urllib.request
import json
import sys

def check(vid):
    try:
        url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={vid}"
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read())
        if "error" not in data and data.get("title"):
            return data["title"]
    except:
        pass
    return None

# Batch 1: Forward flexion / hip hinge candidates
batch1 = [
    "SW_C1A-rejs", "GF4bSwQJ4E0", "K53oCpjNv94", "aPzCLJGLy48",
    "M20VcRfE9lI", "Eg5N2MXvaXM", "XS27m3S5RQM", "7fK6KpLdRDc",
    "KDLRlvFi09c", "sBjSBIuoZw0", "t7Ij4LBV5SA", "G5vZolpWi4M",
    "rMQ15bENBCo", "ZuFREFMm7E0", "MfKFCD04sDY", "PLHY2-nt-y4",
]
# Batch 2: Side bend / flank stretch candidates  
batch2 = [
    "Rl-gE-VPqn8", "AHV-YLXp1k0", "tAUf2jo9900", "Sho3FHwmhiY",
    "xJm6uY3Rplw", "dJjVVb0rDpg", "LT_dFRnmdGs", "a9-aMVsYLdM",
    "C4u7x-0BRWE", "QLiHvHqsDNA", "3p8EBPVZ2Iw", "1rLp0BOJCrA",
]
# Batch 3: Torso rotation candidates
batch3 = [
    "wiD8m8P1XFU", "EvJ_1ywHnTs", "sxMrwPQ1VHc", "R4TFNhOJEqQ",
    "NeJB2PNLbYk", "QFk8i3SAOvQ", "FfOHxfMeUhY", "1-tJlRPOgHM",
    "bO4QYiJfLIU", "s4ubJbT4bOk", "nPLyQAEZY2I", "IJfHvpIYCTI",
]
# Batch 4: Trunk rotation + reach / coordination
batch4 = [
    "4Rp-9_CVY3g", "7Q3MJc0rKYk", "gN_PK5pXmIY", "pn8CbvMZicM",
    "fLm6eB4qYKI", "6Y7l3fUsqKw", "DPYP8P-AjPQ", "E1ht9TCfpfY",
]

for name, batch in [("FORWARD FLEXION", batch1), ("FLANK STRETCH", batch2), 
                     ("TORSO ROTATION", batch3), ("TARGET REACHING", batch4)]:
    print(f"\n=== {name} ===")
    for vid in batch:
        title = check(vid)
        if title:
            print(f"  OK: {vid} - {title[:80]}")
    sys.stdout.flush()

print("\nDone.")
