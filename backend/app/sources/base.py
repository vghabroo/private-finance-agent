from typing import Protocol


class TransactionSource(Protocol):
    def fetch(self) -> dict:
        """Return normalized transactions plus source metadata.

        Shape: {"transactions": [<same dict shape as importer.parse_csv rows>], ...}
        """
        ...
