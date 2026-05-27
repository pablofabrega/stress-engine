class DataProviderError(Exception):
    """Base error for market data provider failures."""


class ProviderConfigurationError(DataProviderError):
    """Raised when a provider cannot run because required credentials are missing."""

