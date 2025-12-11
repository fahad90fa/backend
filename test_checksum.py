#!/usr/bin/env python3
"""
Test script to validate checksum functionality
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.checksum import ChecksumUtils
import hashlib

def test_sha256_computation():
    """Test SHA256 computation"""
    print("=" * 60)
    print("TEST 1: SHA256 Computation")
    print("=" * 60)
    
    test_data = b"Hello, World!"
    computed = ChecksumUtils.compute_sha256(test_data)
    expected = hashlib.sha256(test_data).hexdigest()
    
    print(f"Input: {test_data}")
    print(f"Computed: {computed}")
    print(f"Expected: {expected}")
    print(f"Match: {computed == expected}")
    
    assert computed == expected, "SHA256 computation failed!"
    print("✓ PASSED\n")
    return True

def test_checksum_verification():
    """Test checksum verification"""
    print("=" * 60)
    print("TEST 2: Checksum Verification")
    print("=" * 60)
    
    test_data = b"Test data for verification"
    checksum = ChecksumUtils.compute_sha256(test_data)
    
    # Should verify successfully
    is_valid = ChecksumUtils.verify_checksum(test_data, checksum)
    print(f"Valid checksum verification: {is_valid}")
    assert is_valid, "Checksum verification failed!"
    
    # Should fail with different data
    wrong_data = b"Different data"
    is_invalid = ChecksumUtils.verify_checksum(wrong_data, checksum)
    print(f"Invalid checksum detection: {not is_invalid}")
    assert not is_invalid, "Should have detected invalid checksum!"
    
    print("✓ PASSED\n")
    return True

def test_file_checksum():
    """Test file checksum computation"""
    print("=" * 60)
    print("TEST 3: File Checksum Computation")
    print("=" * 60)
    
    # Create test file
    test_file = "/tmp/test_checksum.txt"
    test_content = b"Test file content for checksum verification\n"
    
    with open(test_file, "wb") as f:
        f.write(test_content)
    
    try:
        # Compute file checksum
        file_checksum = ChecksumUtils.compute_sha256_from_file(test_file)
        data_checksum = ChecksumUtils.compute_sha256(test_content)
        
        print(f"File path: {test_file}")
        print(f"File checksum: {file_checksum}")
        print(f"Data checksum: {data_checksum}")
        print(f"Match: {file_checksum == data_checksum}")
        
        assert file_checksum == data_checksum, "File checksum mismatch!"
        
        # Test get_file_stats
        checksum, size = ChecksumUtils.get_file_stats(test_file)
        print(f"File size: {size} bytes")
        print(f"Size match: {size == len(test_content)}")
        
        assert size == len(test_content), "File size mismatch!"
        assert checksum == file_checksum, "File stats checksum mismatch!"
        
        print("✓ PASSED\n")
        return True
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def test_case_insensitive_comparison():
    """Test case-insensitive checksum comparison"""
    print("=" * 60)
    print("TEST 4: Case-Insensitive Comparison")
    print("=" * 60)
    
    test_data = b"Test case insensitivity"
    checksum_lower = ChecksumUtils.compute_sha256(test_data)
    checksum_upper = checksum_lower.upper()
    
    # Both should verify successfully
    verify_lower = ChecksumUtils.verify_checksum(test_data, checksum_lower)
    verify_upper = ChecksumUtils.verify_checksum(test_data, checksum_upper)
    
    print(f"Lowercase: {checksum_lower}")
    print(f"Uppercase: {checksum_upper}")
    print(f"Verify lowercase: {verify_lower}")
    print(f"Verify uppercase: {verify_upper}")
    
    assert verify_lower, "Lowercase verification failed!"
    assert verify_upper, "Uppercase verification failed!"
    
    print("✓ PASSED\n")
    return True

def test_large_file():
    """Test with larger file"""
    print("=" * 60)
    print("TEST 5: Large File Handling")
    print("=" * 60)
    
    test_file = "/tmp/test_large.bin"
    size_mb = 5
    
    # Create 5MB test file
    print(f"Creating {size_mb}MB test file...")
    with open(test_file, "wb") as f:
        for i in range(size_mb):
            f.write(b"x" * (1024 * 1024))
    
    try:
        import time
        start = time.time()
        checksum, file_size = ChecksumUtils.get_file_stats(test_file)
        elapsed = time.time() - start
        
        print(f"File size: {file_size} bytes ({file_size / (1024*1024):.1f} MB)")
        print(f"Checksum: {checksum}")
        print(f"Time: {elapsed:.3f}s")
        print(f"Speed: {(file_size / (1024*1024)) / elapsed:.1f} MB/s")
        
        assert file_size == size_mb * 1024 * 1024, "File size mismatch!"
        assert len(checksum) == 64, "SHA256 should be 64 hex chars!"
        
        print("✓ PASSED\n")
        return True
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("CHECKSUM FUNCTIONALITY TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("SHA256 Computation", test_sha256_computation),
        ("Checksum Verification", test_checksum_verification),
        ("File Checksum", test_file_checksum),
        ("Case-Insensitive Comparison", test_case_insensitive_comparison),
        ("Large File Handling", test_large_file),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ FAILED: {str(e)}\n")
            failed += 1
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    print("=" * 60 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
