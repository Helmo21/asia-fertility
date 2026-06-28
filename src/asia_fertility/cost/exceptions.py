"""Cost-related exceptions."""
from __future__ import annotations


class CostError(Exception): ...


class PricesNotFound(CostError): ...


class FXNotFound(CostError): ...


class ModelNotInPrices(CostError): ...
