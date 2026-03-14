#!/usr/bin/env python3
"""
Network Diagnostic Script for Video Call Testing
Tests Flask server accessibility from different machines
"""

import socket
import sys
import subprocess
import platform
import requests
from pathlib import Path

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a non-routable address to find the local IP without needing internet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def check_firewall_windows(port):
    """Check if port is open on Windows Firewall"""
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name=Allow Flask Port {port}"],
            capture_output=True, text=True
        )
        return "Allow Flask Port" in result.stdout
    except Exception:
        return None

def check_port_listening(port, host="0.0.0.0"):
    """Check if a port is listening on this machine"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False

def test_flask_endpoint(host, port):
    """Test if Flask is responding to HTTP requests"""
    try:
        response = requests.get(f"http://{host}:{port}/health", timeout=2)
        return response.status_code == 200
    except Exception as e:
        return False

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")

def main():
    print("\n" + "="*60)
    print("  VIDEO CALL NETWORK DIAGNOSTIC TOOL")
    print("="*60)
    
    local_ip = get_local_ip()
    port = 8000
    
    print(f"\n📍 Machine Information:")
    print(f"   Local IP Address: {local_ip}")
    print(f"   Flask Port: {port}")
    print(f"   OS Platform: {platform.system()}")
    
    # Check if Flask is running
    print_header("Checking Flask Server")
    
    if check_port_listening(port):
        print(f"✅ Flask is listening on port {port}")
    else:
        print(f"❌ Flask is NOT listening on port {port}")
        print(f"   Make sure Flask is running with: python main.py")
        sys.exit(1)
    
    # Test health endpoint
    if test_flask_endpoint("127.0.0.1", port):
        print(f"✅ Flask is responding to HTTP requests (localhost)")
    else:
        print(f"❌ Flask is not responding")
        sys.exit(1)
    
    # Check firewall
    print_header("Checking Firewall")
    
    if platform.system() == "Windows":
        fw_status = check_firewall_windows(port)
        if fw_status is None:
            print(f"⚠️  Could not check Windows Firewall status")
        elif fw_status:
            print(f"✅ Port {port} is allowed in Windows Firewall")
        else:
            print(f"❌ Port {port} is NOT in Windows Firewall")
            print(f"\n   To fix, run as Administrator:")
            print(f"   netsh advfirewall firewall add rule name=\"Allow Flask Port {port}\" dir=in action=allow protocol=tcp localport={port}")
    else:
        print(f"ℹ️  Firewall check not implemented for {platform.system()}")
        print(f"   Ensure port {port} is not blocked")
    
    # Network accessibility test
    print_header("Cross-Device Accessibility")
    
    print(f"👥 To access Flask from another laptop:")
    print(f"\n   Machine A (Server): Use the Flask app")
    print(f"   Machine B (Client): Open browser to:")
    print(f"\n   🌐 http://{local_ip}:{port}")
    print(f"\n   DO NOT use: http://localhost:{port}")
    
    # Test endpoints
    print_header("Testing API Endpoints")
    
    endpoints = [
        ("/", "Landing page"),
        ("/health", "Health check"),
        ("/login", "Login page"),
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"http://127.0.0.1:{port}{endpoint}", timeout=2)
            status = "✅" if response.status_code < 400 else "⚠️"
            print(f"{status} {endpoint:30} {description:30} [{response.status_code}]")
        except Exception as e:
            print(f"❌ {endpoint:30} {description:30} [Failed]")
    
    # Video call endpoint test
    print_header("Video Call Configuration")
    
    print("\n🎥 Jitsi Meet Configuration:")
    print("   Server: meet.ffmuc.net")
    print("   Type: Public Jitsi instance")
    print("   Participants: Supports up to 100 per room")
    print("   Status: Open source & free")
    
    # Connection test instructions
    print_header("Quick Connection Test")
    
    print("1️⃣  On Machine A (Server):")
    print(f"   • Start Flask: python main.py")
    print(f"   • Flask will run on: http://{local_ip}:{port}")
    
    print("\n2️⃣  On Machine B (Client - Different Laptop):")
    print(f"   • Open browser to: http://{local_ip}:{port}")
    print(f"   • Login with patient/doctor credentials")
    print(f"   • Schedule or join a video call")
    
    print("\n3️⃣  Expected Results:")
    print("   ✅ Both devices can see Flask login page")
    print("   ✅ Both can login to same appointment")
    print("   ✅ Jitsi Meet video conference loads")
    print("   ✅ Both users appear in video call")
    
    # Troubleshooting
    print_header("Troubleshooting")
    
    print("\n❌ Problem: Can't access Flask from other laptop")
    print("   Solutions:")
    print(f"   • Verify Flask is running: netstat -ano | findstr :{port}")
    print(f"   • Check IP address: ipconfig (Windows) or ifconfig (Mac/Linux)")
    print(f"   • Test connection: ping {local_ip}")
    print(f"   • Check firewall: Enable port {port} in Windows Firewall")
    print(f"   • Try connecting from same network (WiFi/Ethernet)")
    
    print("\n❌ Problem: Video call connects but no video/audio")
    print("   Solutions:")
    print("   • Check camera/microphone permissions in browser")
    print("   • Allow browser to access camera/microphone")
    print("   • Test camera in another app first")
    print("   • Disable browser extensions (ad blockers, privacy tools)")
    print("   • Try a different browser (Chrome/Firefox work best)")
    
    print("\n❌ Problem: Jitsi iframe loads but conference doesn't start")
    print("   Solutions:")
    print("   • Check browser console for errors (F12)")
    print("   • Ensure internet connection available")
    print("   • Try connecting via room URL directly: https://meet.ffmuc.net/rehab-call-123")
    print("   • Check if meet.ffmuc.net is reachable from your network")
    
    # Summary
    print_header("✅ All Checks Complete")
    
    print(f"\n🎯 Next Steps:")
    print(f"1. Ensure Flask is running: python main.py")
    print(f"2. Share this IP with others: {local_ip}:{port}")
    print(f"3. Have both users login and schedule appointment")
    print(f"4. Join video call from both machines")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
