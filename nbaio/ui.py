import typing
from typing import Optional, Union
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

global_console = Console()

from contextlib import nullcontext

class AioUi:
    """User interface component for AioUtils providing rich console output and progress bars."""
    
    def __init__(self, console: Optional[Console] = None):
        self._console = console or global_console

    @property
    def console(self) -> Console:
        return self._console

    def status(self, message: str, ui_enabled: bool = True):
        """Returns a rich status context manager."""
        return self._console.status(message) if ui_enabled else nullcontext()

    def print(self, *args, **kwargs):
        """Prints a message using the rich console."""
        self._console.print(*args, **kwargs)

    def progress(self, ui_enabled: bool = True) -> Union[Progress, nullcontext]:
        """Returns a rich Progress instance configured for downloads."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self._console,
        ) if ui_enabled else nullcontext()

global_ui = AioUi()
