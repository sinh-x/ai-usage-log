"""ServerContext singleton holding all services."""

from .config.settings import get_base_path
from .services.project_service import ProjectService
from .services.session_service import SessionService
from .services.structure_service import StructureService
from .services.tracking_service import TrackingService


class ServerContext:
    """Shared context holding all service instances."""

    def __init__(self) -> None:
        self.base_path = get_base_path()
        self.structure = StructureService(self.base_path)
        self.sessions = SessionService(self.base_path)
        self.tracking = TrackingService(self.base_path)
        self.projects = ProjectService()


_ctx: ServerContext | None = None


def get_context() -> ServerContext:
    """Get or create the shared ServerContext singleton."""
    global _ctx
    if _ctx is None:
        _ctx = ServerContext()
    return _ctx
