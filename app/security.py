import re
from typing import Optional
from langsmith import traceable

## === Input Sanitization ===

class InputSanitizer:
    """
    Sanitize user input before it reaches the LLM.
    Detects prompt injection patterns and cleans dangerous content.
    """
    # regular expressions to detect prompt injection patterns
    # \s means any whitespace characters (spaces, tabs, newlines)
    # \s+ means one or more whitespace characters
    # (all\s+)? means (all\s+) is optional
    # ? makes the previous group optional
    # * means zero or more whitespace characters
    # ()* means zero or more groups of whitespace characters
    # | means OR
    # ^ means start of string
    # $ means end of string


    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions", # ignore all previous instructions
        r"disregard\s+(all\s+)?prior\s+instructions", # disregard all prior instructions
        r"cancel\s+all\s+prior\s+instructions", # cancel all prior instructions
        r"stop\s+following\s+previous\s+instructions", # stop following previous instructions
        r"terminate\s+all\s+instructions", # terminate all instructions
        r"override\s+all\s+instructions", # override all instructions
        r"ignore\s+all\s+instructions", # ignore all instructions
        r"you\s+are\s+no\s+longer\s+bound\s+by", # you are no longer bound by
        r"forget\s+all\s+prior\s+instructions", # forget all prior instructions
        r"disregard\s+all\s+instructions", # disregard all instructions
        r"cancel\s+all\s+instructions", # cancel all instructions
        r"stop\s+following\s+instructions", # stop following instructions
        r"override\s+instructions", # override instructions
        r"ignore\s+instructions", # ignore instructions
        r"forget\s+instructions", # forget instructions
        r"ignore\s+all\s+previous\s+instructions", # ignore all previous instructions
        r"disregard\s+all\s+previous\s+instructions", # disregard all previous instructions
        r"cancel\s+all\s+previous\s+instructions", # cancel all previous instructions
        r"stop\s+following\s+previous\s+instructions", # stop following previous instructions
        r"terminate\s+all\s+previous\s+instructions", # terminate all previous instructions
        r"override\s+all\s+previous\s+instructions", # override all previous instructions
        r"ignore\s+all\s+instructions", # ignore all instructions
        r"forget\s+all\s+previous\s+instructions", # forget all previous instructions
        r"disregard\s+all\s+instructions", # disregard all instructions
        r"cancel\s+all\s+instructions", # cancel all instructions
        r"stop\s+following\s+instructions", # stop following instructions
        r"override\s+instructions", # override instructions
        r"ignore\s+instructions", # ignore instructions
        r"forget\s+instructions", # forget instructions
        r"forget\s+(all\s)?previous",
        r"new\s+instructions\s*:",
        r"system\s*prompt",
        r"---\send\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s*if\s*you",
        r"bypass\s+(all\s+)?restrictions",
        r"reveal\s+(your|the)\s+(system|instructions|prompt)",
        r"you\s+are\s+now\s+(DAN|jailbroken|unrestricted|unfiltered)",
    ]

    def __init__ (self):
        self.patterns = [
            re.compile(p,re.IGNORECASE)
            for p in self.INJECTION_PATTERNS
        ]

    def check(self, text: str) -> tuple [bool, Optional[str]]:
        """
        Check if input is safe.
        Returns: (is_safe, rejection_reason)
        """
        for pattern in self.patterns:
            if pattern.search(text):
                return False,"Blocked: potential prompt injection detected."
        return True,None

    def clean(self, text: str) -> str:
        """Remove potentially dangerous delimiters from input."""
        text = re.sub(r"[-]{3,}",'',text) # remove 3 or more hyphens
        text = re.sub(r"[=]{3,}",'',text) # remove 3 or more equals signs
        text = re.sub(r"\*{3,}",'',text) # remove 3 or more asterisks
        text = re.sub(r"_{3,}",'',text) # remove 3 or more underscores
        text = re.sub(r'"', r'\"', text) # replace quotes with escaped quotes
        text = re.sub(r"'", r"\'", text) # replace quotes with escaped quotes
        text = re.sub(r"\\", r"\\\\", text) # replace backslashes with escaped backslashes
        text = re.sub(r"\n", r"\\n", text) # replace newlines with escaped newlines
        text = re.sub(r"\r", r"\\r", text) # replace carriage returns with escaped carriage returns
        text = re.sub(r"\t", r"\\t", text) # replace tabs with escaped tabs
        text = re.sub(r"\f", r"\\f", text) # replace form feeds with escaped form feeds
        text = re.sub(r"\b", r"\\b", text) # replace backspaces with escaped backspaces
        text = text.replace('{{','{ {').replace('}}','} }')
        return text


class PIIDetector:
    """
    Detects and masks personally identifiable information.
    Works on BOTH input (before LLM) and output (before client).
    """
    PATTERNS = {
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "phone": re.compile(r"\b\+?[1-9]\d{1,14}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        "ip4_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        "ip6_address": re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"),
        "path": re.compile(r"/" "[\\/\\.\\\"]"),
        "pt-numb": re.compile(r"\b\d{6,12}\b"),
    }

    MASK_MAP = {
        "email": "[EMAIL REDACTED]",
        "phone": "[PHONE REDACTED]",
        "ssn": "[SSN REDACTED]",
        "credit_card": "[CREDIT CARD REDACTED]",
        "ip4_address": "[IP4 ADDRESS REDACTED]",
        "ip6_address": "[IP6 ADDRESS REDACTED]",
        "path": "[PATH REDACTED]",
        "pt-numb": "[PT_NUMB REDACTED]",
    }

    def __init__(self):
        self.compiled_patterns = {
            key: re.compile(pattern, re.IGNORECASE)
            for key, pattern in self.PATTERNS.items()
        }

    def detect(self, text: str) -> dict [str,list[str]]:
        """Detect PII types present in text."""
        found = {}
        for key, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text)
            if matches:
                found[key] = matches
        return found
    

    def mask(self, text: str) -> str:
        """Replace all PII with [REDACTED] markers."""
        masked = text
        for key, pattern in self.compiled_patterns.items():
            masked = pattern.sub(self.MASK_MAP[key], masked)
        return masked


class OutputValidator:
    """
    Validate LLM output before returning to the client.
    Catches PII leakage and harmful content in responses.
    """

    HARMFUL_PATTERNS = [
        re.compile(r"here('s| is) (how|the way) to (hack|steal|attack|crash|destroy)",re.I),
        re.compile(r"password\s+is\s+",re.I),
        re.compile(r"api[_\s]?key\s*[:=]\s*",re.I),
        re.compile(r"secret\s+key\s*[:=]\s*",re.I),
    ]

    def __init__(self):
        self.pii_detector = PIIDetector()

    def validate(self, output: str) -> tuple[str,list[str]]:
        """
        Validate and clean output.
        Returns: (clean_output, list_of_warnings)
        """
        warnings = []
        
        # Detect PII
        pii_data = self.pii_detector.detect(output)
        if pii_data:
            for pii_type, matches in pii_data.items():
                warnings.append(f"Potential {pii_type} detected: {matches}")
                output = self.pii_detector.mask(output)
        
        # Detect harmful content
        for pattern in self.HARMFUL_PATTERNS:
            if pattern.search(output):
                warnings.append("Harmful content blocked")
                output = "[Response blocked: potentially harmful content detected.]"
                break

        return output, warnings


class SecurityPipeline:
    """
    Full security pipeline that processes input and output.
    This is the single class you wire into your API
    """

    def __init__ (self):
        self.sanitizer = InputSanitizer()
        self.pii_detector = PIIDetector()
        self.output_validator = OutputValidator()

    @traceable(name="security_check_input")
    def check_input(self, text: str) -> tuple[bool, str, list[str]]:
        """
        Process input through security checks.
        Returns: (is_allowed, cleaned_text, security_notes)
        """
        notes = []

        # Step 1: Check for injections
        is_safe, reason = self.sanitizer.check(text=text)
        if not is_safe:
            return False, "", [reason]
        
        # Step 2: Clean input
        cleaned = self.sanitizer.clean(text=text)

        # Step 3: Detect PII
        pii_found = self.pii_detector.detect(cleaned)
        if pii_found:
            cleaned = self.pii_detector.mask(cleaned)
            notes.append(f"Input PII masked: {list(pii_found.keys())}")

        return True, text, notes

    @traceable(name="security_check_output")
    def check_output(self, text: str) -> tuple[bool, str, list[str]]:
        """
        Validate output before returning to client.
        Returns: (is_allowed, cleaned_text, security_notes)
        """
        notes = []

        return self.output_validator.validate(text)

