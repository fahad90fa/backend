#!/usr/bin/env python3
"""
Test script for MAC Address Sniffer
Tests MAC address capture on Windows, Linux, and macOS
"""

import sys
import platform
from app.core.mac_sniffer import MACAddressSniffer, MACSnifferError
from app.core.mac_manager import MACManager

def test_mac_capture():
    """Test MAC address capture"""
    print("=" * 60)
    print("MAC Address Sniffer Test")
    print("=" * 60)
    print(f"System: {platform.system()}")
    print(f"Platform: {platform.platform()}")
    print(f"Node: {platform.node()}")
    print()
    
    print("Attempting to capture MAC address...")
    print("-" * 60)
    
    mac = MACAddressSniffer.get_system_mac()
    
    if mac:
        print(f"✓ MAC Address captured: {mac}")
        print(f"  Format: {':'.join([f'{ord(c):02x}' for c in mac[:6]])}")
        return True
    else:
        print("✗ Failed to capture MAC address")
        return False


def test_checksum_generation():
    """Test checksum generation"""
    print()
    print("=" * 60)
    print("Checksum Generation Test")
    print("=" * 60)
    
    test_mac = "00:11:22:33:44:55"
    test_user_id = "test-user-123"
    test_secret = "test-secret-key"
    
    checksum = MACAddressSniffer.generate_checksum(test_mac, test_user_id, test_secret)
    
    print(f"MAC Address: {test_mac}")
    print(f"User ID: {test_user_id}")
    print(f"Secret Key: {test_secret}")
    print(f"✓ Generated Checksum: {checksum}")
    
    # Test verification
    is_valid = MACAddressSniffer.verify_mac(
        test_mac, test_mac, checksum, test_user_id, test_secret
    )
    
    if is_valid:
        print("✓ Checksum verification successful")
    else:
        print("✗ Checksum verification failed")
    
    return is_valid


def test_platform_specific_methods():
    """Test platform-specific MAC capture methods"""
    print()
    print("=" * 60)
    print("Platform-Specific Method Test")
    print("=" * 60)
    
    system = platform.system()
    
    print(f"Detected System: {system}")
    print("-" * 60)
    
    try:
        if system == "Windows":
            print("Testing Windows getmac.exe method...")
            mac = MACAddressSniffer._get_mac_windows()
            if mac:
                print(f"✓ Windows method successful: {mac}")
                return True
            else:
                print("✗ Windows method failed")
                return False
        elif system == "Linux":
            print("Testing Linux ip link show method...")
            try:
                mac = MACAddressSniffer._get_mac_linux()
                if mac:
                    print(f"✓ Linux ip link method successful: {mac}")
                    return True
            except MACSnifferError:
                print("Falling back to Linux arp method...")
                mac = MACAddressSniffer._get_mac_linux_arp()
                if mac:
                    print(f"✓ Linux arp fallback successful: {mac}")
                    return True
                else:
                    print("✗ Linux methods failed")
                    return False
        elif system == "Darwin":
            print("Testing macOS networksetup method...")
            mac = MACAddressSniffer._get_mac_macos()
            if mac:
                print(f"✓ macOS method successful: {mac}")
                return True
            else:
                print("✗ macOS method failed")
                return False
        else:
            print(f"Unknown system: {system}")
            print("Attempting fallback method...")
            mac = MACAddressSniffer._get_mac_networkinterfaces()
            if mac:
                print(f"✓ Fallback method successful: {mac}")
                return True
            else:
                print("✗ Fallback method failed")
                return False
    except MACSnifferError as e:
        print(f"✗ Error: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {str(e)}")
        return False


def main():
    """Run all tests"""
    results = []
    
    # Test 1: MAC Capture
    results.append(("MAC Capture", test_mac_capture()))
    
    # Test 2: Checksum Generation
    results.append(("Checksum Generation", test_checksum_generation()))
    
    # Test 3: Platform-Specific Methods
    results.append(("Platform-Specific Methods", test_platform_specific_methods()))
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
