class ServiceError(Exception):
    """A business-rule failure that maps to an HTTP status in the API layer."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail
