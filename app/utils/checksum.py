import hashlib
from typing import Tuple

class ChecksumUtils:
    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def compute_sha256_from_file(file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    @staticmethod
    def verify_checksum(data: bytes, expected_checksum: str) -> bool:
        computed = ChecksumUtils.compute_sha256(data)
        return computed.lower() == expected_checksum.lower()
    
    @staticmethod
    def get_file_stats(file_path: str) -> Tuple[str, int]:
        checksum = ChecksumUtils.compute_sha256_from_file(file_path)
        file_size = __import__('os').path.getsize(file_path)
        return checksum, file_size
