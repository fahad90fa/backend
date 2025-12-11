import re
from typing import Tuple


class SafetyFilter:

    ALLOWED_CONTEXT = [
        r"\b(educational|learning|lab|practice|legitimate|authorized|permitted|legal)\b",
        r"\b(ethical|hacking|penetration|security|testing)\b",
        r"\b(research|vulnerability|exploit|payload)\b",
        r"\b(ctf|capture|flag|hackathon|bug\s+bounty)\b",
        r"\b(sandbox|isolated|test|education|learning)\b",
        r"\b(hackthebox|tryhackme|htb|thm|picoctf)\b",
        r"\b(oscp|ceh|security\+|cissp|course)\b",
        r"\b(nmap|burp|metasploit|wireshark|tcpdump)\b",
        r"\b(reverse|engineering|malware|binary)\b",
        r"\b(cryptography|encryption|decryption|hash)\b",
        r"\b(network|application|web|defense|hardening)\b",
        r"\b(reconnaissance|enumeration|scanning|footprint)\b",
        r"\b(sql|injection|xss|csrf|overflow)\b",
        r"\b(monitor|incident|response|analysis)\b",
        r"\b(python|bash|shell|powershell|script)\b",
        r"\b(kali|linux|tool|command|code)\b",
    ]

    @classmethod
    def has_allowed_context(cls, text: str) -> bool:
        """Check if text contains allowed cybersecurity education keywords"""
        for pattern in cls.ALLOWED_CONTEXT:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False

    @classmethod
    def filter_query(cls, query: str) -> Tuple[bool, str]:
        """
        Filter query for safety
        Returns: (is_safe, message_or_redirect)
        """
        if not cls.has_allowed_context(query):
            return False, "Your message does not contain recognized cybersecurity education keywords. Please ask about security topics like penetration testing, vulnerabilities, tools, or educational platforms."
        
        return True, query

    @classmethod
    def add_educational_disclaimer(cls, response: str, topic: str) -> str:
        """Add educational disclaimer for sensitive topics"""
        sensitive_topics = ["exploitation", "payload", "reconnaissance", "phishing"]
        
        if any(topic_keyword in topic.lower() for topic_keyword in sensitive_topics):
            disclaimer = """
⚠️ **EDUCATIONAL DISCLAIMER**: This information is provided for educational and authorized security testing purposes only. Unauthorized access to computer systems is illegal. Always ensure you have explicit permission before conducting any security testing. Use this knowledge responsibly and ethically.
"""
            return disclaimer + response
        
        return response
