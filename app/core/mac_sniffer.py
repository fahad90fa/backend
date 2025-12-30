import subprocess
import re
import hashlib
import os
import platform
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MACSnifferError(Exception):
    """Exception for MAC address sniffer errors"""
    pass


class MACAddressSniffer:
    """
    Low-level MAC address sniffer for Windows, Linux, and macOS.
    Never uses WebRTC, browser APIs, or third-party services.
    Captures the MAC address of the first active network interface (Ethernet, WiFi, etc.)
    """

    @staticmethod
    def _log_available_interfaces() -> None:
        """Debug: Log all available network interfaces"""
        try:
            import glob
            net_dirs = glob.glob("/sys/class/net/*/address")
            if net_dirs:
                interfaces = [path.split('/')[-2] for path in net_dirs]
                logger.debug(f"Available network interfaces: {', '.join(interfaces)}")
        except:
            pass

    @staticmethod
    def get_system_mac() -> Optional[str]:
        """
        Capture system MAC address using platform-specific methods.
        Priority: getmac.exe (Windows) > ip link show (Linux) > networksetup (macOS) > /sys/class/net (Linux) > os.networkinterfaces()
        
        Returns:
            MAC address string (e.g., "A1:B2:C3:D4:E5:F6") or None if unable to capture
        """
        system = platform.system()
        logger.info(f"Detecting system: {system}")
        MACAddressSniffer._log_available_interfaces()
        
        try:
            if system == "Windows":
                return MACAddressSniffer._get_mac_windows()
            elif system == "Linux":
                return MACAddressSniffer._get_mac_linux()
            elif system == "Darwin":  # macOS
                return MACAddressSniffer._get_mac_macos()
            else:
                logger.warning(f"Unknown system: {system}, falling back to networkinterfaces")
                return MACAddressSniffer._get_mac_networkinterfaces()
        except MACSnifferError as e:
            logger.error(f"MAC sniffer error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error capturing MAC: {str(e)}")
            return None

    @staticmethod
    def _get_mac_windows() -> Optional[str]:
        """Windows: Use getmac.exe command"""
        try:
            output = subprocess.check_output(
                ["getmac.exe", "/format", "csv"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True
            )
            
            lines = output.strip().split("\n")
            if len(lines) < 2:
                logger.warning("Invalid getmac output, using fallback")
                return MACAddressSniffer._get_mac_serverless_fallback()
            
            # First data line contains the MAC
            mac_line = lines[1]
            mac_match = re.search(r"([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})", mac_line)
            
            if mac_match:
                mac = mac_match.group(1).upper()
                logger.info(f"Captured MAC (Windows): {mac}")
                return mac
            else:
                logger.warning("Could not parse getmac output, using fallback")
                return MACAddressSniffer._get_mac_serverless_fallback()
        except subprocess.TimeoutExpired:
            logger.warning("getmac.exe timeout, using fallback")
            return MACAddressSniffer._get_mac_serverless_fallback()
        except FileNotFoundError:
            logger.warning("getmac.exe not found, using fallback")
            return MACAddressSniffer._get_mac_serverless_fallback()
        except Exception as e:
            logger.warning(f"Windows MAC capture failed: {str(e)}, using fallback")
            return MACAddressSniffer._get_mac_serverless_fallback()

    @staticmethod
    def _get_mac_linux() -> Optional[str]:
        """Linux: Use ip link show command, fallback to /sys/class/net"""
        try:
            output = subprocess.check_output(
                ["ip", "link", "show"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True
            )
            
            # Parse to get interface name and MAC address
            lines = output.split('\n')
            current_interface = None
            
            for line in lines:
                # Match interface line like: "1: lo: <LOOPBACK,UP,LOWER_UP>"
                if_match = re.match(r"^\d+:\s+([a-zA-Z0-9\-]+):", line)
                if if_match:
                    current_interface = if_match.group(1)
                    # Skip loopback
                    if current_interface == 'lo':
                        current_interface = None
                
                # Match MAC address line like: "link/ether aa:bb:cc:dd:ee:ff"
                mac_match = re.search(r"link/ether\s+([0-9a-f:]{17})", line, re.IGNORECASE)
                if mac_match and current_interface:
                    mac = mac_match.group(1).upper()
                    logger.info(f"Captured MAC (Linux via ip link show): {mac} from interface '{current_interface}'")
                    return mac
            
            logger.debug("No non-loopback MAC address found in ip link output, trying /sys/class/net")
            return MACAddressSniffer._get_mac_linux_sysfs()
        except subprocess.TimeoutExpired:
            logger.debug("ip link show timeout, trying /sys/class/net")
            return MACAddressSniffer._get_mac_linux_sysfs()
        except FileNotFoundError:
            logger.debug("ip command not found, trying /sys/class/net")
            return MACAddressSniffer._get_mac_linux_sysfs()
        except Exception as e:
            logger.debug(f"Linux MAC capture failed: {str(e)}, trying /sys/class/net")
            return MACAddressSniffer._get_mac_linux_sysfs()

    @staticmethod
    def _get_mac_linux_sysfs() -> Optional[str]:
        """Linux fallback: Read MAC directly from /sys/class/net/*/address"""
        try:
            import glob
            
            net_dirs = glob.glob("/sys/class/net/*/address")
            
            if not net_dirs:
                logger.debug("No network interfaces found in /sys/class/net")
                return MACAddressSniffer._get_mac_linux_arp()
            
            logger.debug(f"Found {len(net_dirs)} network interface(s) in /sys/class/net")
            
            for addr_file in net_dirs:
                try:
                    # Extract interface name from path: /sys/class/net/eth0/address -> eth0
                    interface_name = addr_file.split('/')[-2]
                    
                    with open(addr_file, 'r') as f:
                        mac = f.read().strip().upper()
                        if mac and re.match(r"^([0-9A-F:]{17})$", mac):
                            logger.info(f"Captured MAC (Linux via /sys/class/net): {mac} from interface '{interface_name}'")
                            return mac
                except Exception as e:
                    logger.debug(f"Failed to read {addr_file}: {e}")
                    continue
            
            logger.debug("No valid MAC found in /sys/class/net, trying arp command")
            return MACAddressSniffer._get_mac_linux_arp()
        except Exception as e:
            logger.debug(f"sysfs method failed: {str(e)}, trying arp command")
            return MACAddressSniffer._get_mac_linux_arp()

    @staticmethod
    def _get_mac_linux_arp() -> Optional[str]:
        """Linux fallback: Use arp -a command or read /proc/net/arp"""
        try:
            output = subprocess.check_output(
                ["arp", "-a"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True
            )
            
            mac_matches = re.findall(r"([0-9a-f:]{17})", output, re.IGNORECASE)
            
            if mac_matches:
                mac = mac_matches[0].upper()
                logger.info(f"Captured MAC (Linux via arp): {mac}")
                return mac
            else:
                logger.debug("No MAC address found in arp output, trying /proc/net/arp")
                return MACAddressSniffer._get_mac_linux_proc()
        except FileNotFoundError:
            logger.debug("arp command not found, trying /proc/net/arp")
            return MACAddressSniffer._get_mac_linux_proc()
        except Exception as e:
            logger.debug(f"Linux ARP fallback failed: {str(e)}, trying /proc/net/arp")
            return MACAddressSniffer._get_mac_linux_proc()

    @staticmethod
    def _get_mac_linux_proc() -> Optional[str]:
        """Linux fallback: Read ARP table from /proc/net/arp"""
        try:
            with open("/proc/net/arp", "r") as f:
                content = f.read()
                mac_matches = re.findall(r"([0-9A-Fa-f:]{17})", content)
                
                if mac_matches:
                    mac = mac_matches[0].upper()
                    logger.info(f"Captured MAC (Linux via /proc/net/arp): {mac}")
                    return mac
                else:
                    logger.debug("No MAC found in /proc/net/arp")
                    return MACAddressSniffer._get_mac_python_socket()
        except FileNotFoundError:
            logger.debug("/proc/net/arp not found")
            return MACAddressSniffer._get_mac_python_socket()
        except Exception as e:
            logger.debug(f"Failed to read /proc/net/arp: {str(e)}")
            return MACAddressSniffer._get_mac_python_socket()

    @staticmethod
    def _get_mac_python_socket() -> Optional[str]:
        """Python socket-based MAC lookup (works in most Linux environments)"""
        try:
            import socket
            import struct
            import fcntl
            
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((ip_address, 80))
            ip = s.getsockname()[0]
            s.close()
            
            mac = fcntl.ioctl(
                socket.socket(socket.AF_PACKET, socket.SOCK_RAW),
                0x8927,
                struct.pack('256s', ip.encode('utf-8')[:15])
            )[18:24]
            mac = ":".join(map(lambda x: "%02x" % x, mac)).upper()
            logger.info(f"Captured MAC (Python socket): {mac}")
            return mac
        except Exception as e:
            logger.debug(f"Python socket method failed: {str(e)}")
            return MACAddressSniffer._get_mac_python_ifconfig()

    @staticmethod
    def _get_mac_python_ifconfig() -> Optional[str]:
        """Parse ifconfig output with Python (no external process needed for parsing)"""
        try:
            output = subprocess.check_output(
                ["ifconfig"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True
            )
            
            mac_matches = re.findall(r"(?:HWaddr|lladdr|ether)\s+([0-9A-Fa-f:]{17})", output, re.IGNORECASE)
            
            if mac_matches:
                mac = mac_matches[0].upper()
                logger.info(f"Captured MAC (Linux via ifconfig): {mac}")
                return mac
            else:
                logger.debug("No MAC found in ifconfig output")
                return MACAddressSniffer._get_mac_proc_net_dev()
        except FileNotFoundError:
            logger.debug("ifconfig command not found")
            return MACAddressSniffer._get_mac_proc_net_dev()
        except Exception as e:
            logger.debug(f"ifconfig parsing failed: {str(e)}")
            return MACAddressSniffer._get_mac_proc_net_dev()

    @staticmethod
    def _get_mac_proc_net_dev() -> Optional[str]:
        """Read network device list from /proc/net/dev"""
        try:
            with open("/proc/net/dev", "r") as f:
                content = f.read()
                lines = content.split('\n')
                
                for line in lines[2:]:
                    if line.strip() and not line.startswith('lo'):
                        interface = line.split(':')[0].strip()
                        if interface and interface != 'lo':
                            addr_file = f"/sys/class/net/{interface}/address"
                            try:
                                with open(addr_file, 'r') as af:
                                    mac = af.read().strip().upper()
                                    if mac and re.match(r"^([0-9A-F:]{17})$", mac):
                                        logger.info(f"Captured MAC (Linux via /proc/net/dev + /sys): {mac}")
                                        return mac
                            except:
                                continue
                
                logger.debug("No valid MAC found via /proc/net/dev")
                return MACAddressSniffer._get_mac_serverless_fallback()
        except Exception as e:
            logger.debug(f"Failed to read /proc/net/dev: {str(e)}")
            return MACAddressSniffer._get_mac_serverless_fallback()

    @staticmethod
    def _get_mac_macos() -> Optional[str]:
        """macOS: Use networksetup command"""
        try:
            # Get list of all hardware ports
            output = subprocess.check_output(
                ["networksetup", "-listallhardwareports"],
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True
            )
            
            mac_matches = re.findall(r"Address:\s+([0-9a-f:]{17})", output, re.IGNORECASE)
            
            if mac_matches:
                # Get the first active interface MAC
                mac = mac_matches[0].upper()
                logger.info(f"Captured MAC (macOS): {mac}")
                return mac
            else:
                logger.warning("No MAC address found in networksetup output, using fallback")
                return MACAddressSniffer._get_mac_serverless_fallback()
        except subprocess.TimeoutExpired:
            logger.warning("networksetup timeout, using fallback")
            return MACAddressSniffer._get_mac_serverless_fallback()
        except FileNotFoundError:
            logger.warning("networksetup command not found, using fallback")
            return MACAddressSniffer._get_mac_serverless_fallback()
        except Exception as e:
            logger.warning(f"macOS MAC capture failed: {str(e)}, using fallback")
            return MACAddressSniffer._get_mac_serverless_fallback()

    @staticmethod
    def _get_mac_networkinterfaces() -> Optional[str]:
        """Fallback: Use Python's os.networkinterfaces() (platform-agnostic)"""
        try:
            import os
            
            interfaces = os.popen("ipconfig getmac 2>/dev/null || ip link show 2>/dev/null || ifconfig 2>/dev/null").read()
            mac_match = re.search(r"([0-9a-f:]{17})", interfaces, re.IGNORECASE)
            
            if mac_match:
                mac = mac_match.group(1).upper()
                logger.info(f"Captured MAC (fallback): {mac}")
                return mac
            else:
                logger.warning("No MAC address found via fallback method, using serverless-safe fallback")
                return MACAddressSniffer._get_mac_serverless_fallback()
        except Exception as e:
            logger.warning(f"Fallback MAC capture failed, trying serverless-safe method: {str(e)}")
            return MACAddressSniffer._get_mac_serverless_fallback()

    @staticmethod
    def _get_mac_serverless_fallback() -> Optional[str]:
        """
        Serverless-safe fallback: Generate stable device fingerprint from environment.
        Used when running on Vercel, AWS Lambda, or other containerized environments
        where system commands are unavailable.
        """
        try:
            import os
            import uuid
            
            hostname = os.getenv("HOSTNAME", platform.node())
            vercel_deployment_id = os.getenv("VERCEL_DEPLOYMENT_ID", "")
            aws_lambda_function = os.getenv("AWS_LAMBDA_FUNCTION_NAME", "")
            
            fingerprint_base = f"{hostname}-{vercel_deployment_id or aws_lambda_function or 'serverless'}"
            
            fingerprint_hash = hashlib.sha256(fingerprint_base.encode()).hexdigest()[:12]
            mac = f"{fingerprint_hash[0:2]}:{fingerprint_hash[2:4]}:{fingerprint_hash[4:6]}:{fingerprint_hash[6:8]}:{fingerprint_hash[8:10]}:{fingerprint_hash[10:12]}"
            mac = mac.upper()
            
            logger.info(f"Generated serverless device fingerprint MAC: {mac}")
            return mac
        except Exception as e:
            logger.error(f"Serverless fallback failed: {str(e)}")
            return None

    @staticmethod
    def generate_checksum(mac: str, user_id: str, secret_key: str) -> str:
        """
        Generate SHA256 checksum for MAC verification.
        
        Args:
            mac: MAC address (e.g., "A1:B2:C3:D4:E5:F6")
            user_id: User ID (UUID)
            secret_key: Secret verification key from environment
            
        Returns:
            SHA256 checksum as hex string
        """
        combined = f"{mac}|{user_id}|{secret_key}"
        checksum = hashlib.sha256(combined.encode()).hexdigest()
        logger.debug(f"Generated checksum for user {user_id}")
        return checksum

    @staticmethod
    def verify_mac(current_mac: str, stored_mac: str, stored_checksum: str, 
                  user_id: str, secret_key: str) -> bool:
        """
        Verify that the current MAC matches the stored MAC using checksum.
        
        Args:
            current_mac: Currently captured MAC address
            stored_mac: MAC address stored in database
            stored_checksum: Checksum stored in database
            user_id: User ID
            secret_key: Secret verification key
            
        Returns:
            True if MAC is valid and matches, False otherwise
        """
        # Normalize MAC addresses (remove colons, uppercase)
        current_normalized = current_mac.replace(":", "").upper()
        stored_normalized = stored_mac.replace(":", "").upper()
        
        if current_normalized != stored_normalized:
            logger.warning(f"MAC mismatch for user {user_id}: {current_mac} != {stored_mac}")
            return False
        
        # Verify checksum
        expected_checksum = MACAddressSniffer.generate_checksum(current_mac, user_id, secret_key)
        
        if expected_checksum != stored_checksum:
            logger.warning(f"Checksum verification failed for user {user_id}")
            return False
        
        logger.info(f"MAC verification successful for user {user_id}")
        return True
