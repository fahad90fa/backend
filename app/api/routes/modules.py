from fastapi import APIRouter, Depends
from app.models import User
from app import security

router = APIRouter(prefix="/modules", tags=["modules"])


MODULES = [
    {
        "id": "reconnaissance",
        "title": "Reconnaissance",
        "description": "Learn information gathering techniques and passive/active reconnaissance methods",
        "topics": [
            "OSINT (Open Source Intelligence)",
            "Domain Enumeration",
            "Port Scanning",
            "Service Discovery",
            "Network Mapping",
            "Footprinting"
        ]
    },
    {
        "id": "exploitation",
        "title": "Exploitation",
        "description": "Understand exploitation techniques and vulnerability assessment",
        "topics": [
            "Common Vulnerabilities (OWASP Top 10)",
            "Vulnerability Assessment",
            "Exploitation Frameworks",
            "Post-Exploitation",
            "Privilege Escalation",
            "Lateral Movement"
        ]
    },
    {
        "id": "payloads",
        "title": "Payloads & Shells",
        "description": "Learn about payload generation and remote code execution",
        "topics": [
            "Payload Generation",
            "Reverse Shells",
            "Bind Shells",
            "Encoded Payloads",
            "Multi-Stage Payloads",
            "Handler Setup"
        ]
    },
    {
        "id": "python-security",
        "title": "Python Security Scripting",
        "description": "Master Python for security automation and tool development",
        "topics": [
            "Socket Programming",
            "Network Analysis",
            "File Operations",
            "Process Management",
            "Cryptography",
            "Web Scraping"
        ]
    },
    {
        "id": "kali-tools",
        "title": "Kali Linux Tools",
        "description": "Comprehensive guide to Kali Linux penetration testing tools",
        "topics": [
            "Information Gathering Tools",
            "Vulnerability Analysis Tools",
            "Exploitation Tools",
            "Forensics Tools",
            "Wireless Tools",
            "Tool Chaining"
        ]
    },
    {
        "id": "defense",
        "title": "Defense Strategies",
        "description": "Learn defensive security and mitigation techniques",
        "topics": [
            "Network Security",
            "Application Security",
            "Endpoint Security",
            "Incident Response",
            "Threat Detection",
            "Security Hardening"
        ]
    }
]


@router.get("/")
async def get_modules(current_user: User = Depends(security.get_current_user)):
    return MODULES


@router.get("/{module_id}")
async def get_module(
    module_id: str,
    current_user: User = Depends(security.get_current_user)
):
    for module in MODULES:
        if module["id"] == module_id:
            return module
    
    return {"error": "Module not found"}
