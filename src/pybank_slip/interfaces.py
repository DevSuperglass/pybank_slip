import abc
from typing import Dict, Any, Optional

class BaseBankAdapter(abc.ABC):
    """
    Abstract base class for standard operations across all banks.
    All bank adapters must implement these standard operations.
    """

    def sanitize_payload(self, data: Any) -> Any:
        """Recursively rounds all float values in dictionaries and lists to 2 decimal places."""
        if isinstance(data, dict):
            return {k: self.sanitize_payload(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_payload(v) for v in data]
        elif isinstance(data, float):
            return round(data, 2)
        return data

    @abc.abstractmethod
    def generate_bank_slip(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate (issue) a new bank slip."""
        pass

    @abc.abstractmethod
    def list_bank_slips(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List existing bank slips with optional filters."""
        pass

    @abc.abstractmethod
    def cancel_bank_slip(self, bank_slip_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cancel an existing bank slip."""
        pass

    @abc.abstractmethod
    def edit_bank_slip(self, bank_slip_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Edit an existing bank slip."""
        pass

    def search_workspaces(self) -> dict:
        raise NotImplementedError

    def create_workspace(self, payload: dict) -> dict:
        raise NotImplementedError
    def edit_workspace(self, workspace_id: str, payload: dict) -> dict:
        raise NotImplementedError
    def delete_workspace(self, workspace_id: str) -> None:
        raise NotImplementedError
