"""Custom exceptions for bok-ecos-mcp."""

from __future__ import annotations


class EcosError(Exception):
    """Base exception for this project."""


class ConfigError(EcosError):
    """Raised when configuration is invalid or missing."""


class EcosValidationError(EcosError):
    """Raised for invalid user input/arguments."""


class EcosNetworkError(EcosError):
    """Raised for network and timeout failures."""


class EcosAPIError(EcosError):
    """Raised when ECOS API returns an error result."""


class EcosRateLimitError(EcosError):
    """Raised when requests are throttled and retries are exhausted."""
