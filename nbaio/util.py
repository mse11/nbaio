"""Utility functions for downloads, extraction, and subprocess operations.

This module provides the AioUtils class with static methods for:
- Downloading files with progress bars
- Parallel downloading
- ZIP/tar extraction
- Running subprocess commands asynchronously

Uses anyio for async operations (compatible with asyncio and trio backends).
Supports both interactive (with UI) and non-interactive modes via ui_enabled flags.
"""

from typing import List, Union
import os
import shutil
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, List, Callable
from contextlib import nullcontext
import anyio
import httpx
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

console = Console()


class AioUtils:
    """Utility class for asynchronous operations using anyio."""

    # ============================================================================
    # DOWNLOAD
    # ============================================================================

    @staticmethod
    async def _download_core(
        url: str,
        dest_path: Path,
        verify_ssl: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> tuple[bool, Optional[str], Optional[int]]:
        """Core download functionality without UI.
        
        Args:
            url: URL to download from
            dest_path: Destination file path
            verify_ssl: Whether to verify SSL certificates
            progress_callback: Optional callback for progress updates (receives bytes downloaded)
            
        Returns:
            Tuple of (success, error_message, total_size)
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with httpx.AsyncClient(verify=verify_ssl, timeout=3600.0) as client:
                async with client.stream('GET', url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    
                    async with await anyio.open_file(dest_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            await f.write(chunk)
                            if progress_callback:
                                progress_callback(len(chunk))
                    
                    return (True, None, total_size)
                    
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            return (False, str(e), None)

    @staticmethod
    async def download_file(
        url: str,
        dest_path: Path,
        expected_size: Optional[int] = None,
        verify_ssl: bool = True,
        ui_enabled: bool = False,
        progress: Optional[Progress] = None,
    ) -> bool:
        """Download a file asynchronously with optional progress tracking.
        
        Args:
            url: URL to download from
            dest_path: Destination file path
            expected_size: Expected file size for validation
            verify_ssl: Whether to verify SSL certificates
            ui_enabled: Whether to show UI elements (progress/messages)
            progress: Rich Progress instance for tracking (only used if ui_enabled=True)
            
        Returns:
            True if download successful, False otherwise
        """
        dest_path = Path(dest_path)
        
        task_id = None
        
        # Setup progress tracking if UI is enabled
        if ui_enabled and progress:
            task_id = progress.add_task(
                f"[cyan]Downloading {dest_path.name}",
                total=0  # Will be updated when we know the size
            )
        
        # Define progress callback
        def on_progress(chunk_size: int):
            if ui_enabled and progress and task_id is not None:
                progress.update(task_id, advance=chunk_size)
        
        # Download using core functionality
        success, error, total_size = await AioUtils._download_core(
            url,
            dest_path,
            verify_ssl=verify_ssl,
            progress_callback=on_progress if ui_enabled and progress else None,
        )
        
        # Update total size for progress bar
        if ui_enabled and progress and task_id is not None and total_size:
            progress.update(task_id, total=total_size)
        
        # Validate size if expected
        if success and expected_size and dest_path.stat().st_size != expected_size:
            if ui_enabled:
                console.print(
                    f"[yellow]Warning: Downloaded file size mismatch for {dest_path.name}"
                )
            return False
        
        # Show error message if failed
        if not success and ui_enabled:
            console.print(f"[red]Error downloading {url}: {error}")
        
        return success

    @staticmethod
    async def download_files(
        downloads: List[tuple[str, Path]],
        max_concurrent: int = 5,
        ui_enabled: bool = False,
    ) -> List[bool]:
        """Download multiple files in parallel.
        
        Args:
            downloads: List of (url, dest_path) tuples
            max_concurrent: Maximum concurrent downloads
            ui_enabled: Whether to show UI elements (progress bars/messages)
            
        Returns:
            List of success flags for each download
        """
        # Use progress context only if UI is enabled
        progress_ctx = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) if ui_enabled else nullcontext()
        
        with progress_ctx as progress:
            limiter = anyio.CapacityLimiter(max_concurrent)
            
            results = [False] * len(downloads)
            
            async def download_with_limiter(index: int, url: str, dest: Path):
                async with limiter:
                    results[index] = await AioUtils.download_file(
                        url, 
                        dest, 
                        ui_enabled=ui_enabled,
                        progress=progress if ui_enabled else None
                    )
            
            async with anyio.create_task_group() as tg:
                for i, (url, dest) in enumerate(downloads):
                    tg.start_soon(download_with_limiter, i, url, dest)
            
            return results

    # ============================================================================
    # EXTRACT ZIP
    # ============================================================================
    @staticmethod
    async def _extract_zip_core(
        zip_path: Path,
        dest_dir: Path,
        remove_after: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Core ZIP extraction functionality without UI.
        
        Args:
            zip_path: Path to ZIP file
            dest_dir: Destination directory
            remove_after: Whether to remove ZIP after extraction
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            def _extract():
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(dest_dir)
            
            await anyio.to_thread.run_sync(_extract)
            
            if remove_after and zip_path.exists():
                zip_path.unlink()
            
            return (True, None)
            
        except Exception as e:
            return (False, str(e))

    @staticmethod
    async def extract_zip(
        zip_path: Path,
        dest_dir: Path,
        remove_after: bool = False,
        ui_enabled: bool = False,
    ) -> bool:
        """Extract a ZIP archive asynchronously.
        
        Args:
            zip_path: Path to ZIP file
            dest_dir: Destination directory
            remove_after: Whether to remove ZIP after extraction
            ui_enabled: Whether to show UI elements (status/messages)
            
        Returns:
            True if successful, False otherwise
        """
        # Use status context only if UI is enabled
        status_ctx = console.status(f"[cyan]Extracting {zip_path.name}...") if ui_enabled else nullcontext()
        
        with status_ctx:
            success, error = await AioUtils._extract_zip_core(zip_path, dest_dir, remove_after)
        
        # Show result messages if UI is enabled
        if ui_enabled:
            if success:
                console.print(f"[green]✓ Extracted {zip_path.name}")
            else:
                console.print(f"[red]Error extracting {zip_path}: {error}")
        
        return success
        
    # ============================================================================
    # EXTRACT TAR
    # ============================================================================
    @staticmethod
    async def _extract_tar_core(
        tar_path: Path,
        dest_dir: Path,
        remove_after: bool = True,
        filter: str = 'data',
    ) -> tuple[bool, Optional[str]]:
        """Core TAR extraction functionality without UI.
        
        Args:
            tar_path: Path to TAR file
            dest_dir: Destination directory
            remove_after: Whether to remove TAR after extraction
            filter: Filter level for tarfile.extractall ('data', 'tar', or 'fully_trusted')
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            def _extract():
                with tarfile.open(tar_path, 'r:*') as tar_ref:
                    tar_ref.extractall(dest_dir, filter=filter)

            await anyio.to_thread.run_sync(_extract)
            
            if remove_after and tar_path.exists():
                tar_path.unlink()
            
            return (True, None)
            
        except Exception as e:
            return (False, str(e))

    @staticmethod
    async def extract_tar(
        tar_path: Path,
        dest_dir: Path,
        remove_after: bool = True,
        ui_enabled: bool = False,
        filter: str = 'data',
    ) -> bool:
        """Extract a TAR archive asynchronously.
        
        Args:
            tar_path: Path to TAR file
            dest_dir: Destination directory
            remove_after: Whether to remove TAR after extraction
            ui_enabled: Whether to show UI elements (status/messages)
            filter: Filter level for tarfile.extractall ('data', 'tar', or 'fully_trusted')
            
        Returns:
            True if successful, False otherwise
        """
        # Use status context only if UI is enabled
        status_ctx = console.status(f"[cyan]Extracting {tar_path.name}...") if ui_enabled else nullcontext()
        
        with status_ctx:
            success, error = await AioUtils._extract_tar_core(tar_path, dest_dir, remove_after, filter=filter)
        
        # Show result messages if UI is enabled
        if ui_enabled:
            if success:
                console.print(f"[green]✓ Extracted {tar_path.name}")
            else:
                console.print(f"[red]Error extracting {tar_path}: {error}")
        
        return success

    # ============================================================================
    # SHELL
    # ============================================================================

    @staticmethod
    async def shell_cmd(
        command: Union[str, List[str]],
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        ui_enabled: bool = False,
    ) -> tuple[int, str, str]:
        """Run a subprocess command asynchronously.
        
        Args:
            command: Command as string (runs via shell) or list of strings
            cwd: Working directory
            env: Environment variables
            capture_output: Whether to capture stdout/stderr
            ui_enabled: Whether to show error messages
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """

        if isinstance(command, str) and os.name == 'nt':
            # Check for POSIX-like environment on Windows (e.g., Git Bash)
            if os.environ.get("MSYSTEM") or os.environ.get("SHELL"):
                shell_path = shutil.which("bash") or shutil.which("sh")
                if shell_path:
                    command = [shell_path, "-c", command]

        try:
            if capture_output:
                process = await anyio.run_process(
                    command,
                    cwd=cwd,
                    env=env,
                    check=False,
                )
                result = (
                    process.returncode,
                    process.stdout.decode('utf-8', errors='ignore') if process.stdout else "",
                    process.stderr.decode('utf-8', errors='ignore') if process.stderr else "",
                )

                if ui_enabled:
                    console.print(f"Command: {command}: {result}")

                return result
            else:
                process = await anyio.run_process(
                    command,
                    cwd=cwd,
                    env=env,
                    check=False,
                    stdout=None,
                    stderr=None,
                )
                return (process.returncode, "", "")
                
        except Exception as e:
            if ui_enabled:
                console.print(f"[red]Error running command: {command}: {e}")
            return (-1, "", str(e))

    @staticmethod
    async def shell_cmds(
        commands: List[Union[str, List[str]]],
        max_concurrent: int = 5,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        ui_enabled: bool = False,
    ) -> List[tuple[int, str, str]]:
        """Run multiple subprocess commands concurrently.
        
        Args:
            commands: List of commands (each can be a string or list of strings)
            max_concurrent: Maximum concurrent commands
            cwd: Working directory
            env: Environment variables
            capture_output: Whether to capture stdout/stderr
            ui_enabled: Whether to show error messages
            
        Returns:
            List of (return_code, stdout, stderr) tuples
        """
        limiter = anyio.CapacityLimiter(max_concurrent)
        results = [(-1, "", "")] * len(commands)
        
        async def run_with_limiter(index: int, cmd: Union[str, List[str]]):
            async with limiter:
                results[index] = await AioUtils.shell_cmd(
                    cmd,
                    cwd=cwd,
                    env=env,
                    capture_output=capture_output,
                    ui_enabled=ui_enabled
                )
        
        async with anyio.create_task_group() as tg:
            for i, cmd in enumerate(commands):
                tg.start_soon(run_with_limiter, i, cmd)
        
        return results

    # ============================================================================
    # SHELL GIT
    # ============================================================================

    @staticmethod
    async def shell_cmds_git_clone(
        clones: List[tuple[str, Optional[str]]],
        max_concurrent: int = 5,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        capture_output: bool = True,
        ui_enabled: bool = False,
    ) -> List[tuple[int, str, str]]:
        """Run multiple git clone commands concurrently.
        
        Args:
            clones: List of (url, dest_dir) tuples. dest_dir can be None or empty.
            max_concurrent: Maximum concurrent clones
            cwd: Working directory
            env: Environment variables
            capture_output: Whether to capture stdout/stderr
            ui_enabled: Whether to show error messages
            
        Returns:
            List of (return_code, stdout, stderr) tuples
        """
        commands = []
        for url, dest in clones:
            cmd = ["git", "clone", url]
            if dest:
                cmd.append(str(dest))
            commands.append(cmd)
            
        return await AioUtils.shell_cmds(
            commands,
            max_concurrent=max_concurrent,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            ui_enabled=ui_enabled,
        )
    # ============================================================================
    # FILE SYSTEM
    # ============================================================================

    @staticmethod
    def check_file_size(file_path: Path, expected_size: int, tolerance: float = 0.01) -> bool:
        """Check if file size matches expected size within tolerance.
        
        Args:
            file_path: Path to file to check
            expected_size: Expected size in bytes
            tolerance: Acceptable deviation as percentage (default 1%)
            
        Returns:
            True if size matches within tolerance
        """
        if not file_path.exists():
            return False
        
        actual_size = file_path.stat().st_size
        diff_ratio = abs(actual_size - expected_size) / expected_size
        
        return diff_ratio <= tolerance

    @staticmethod
    def remove_directory(
        dir_path: Path,
        ui_enabled: bool = False,
        custom_console: Optional[Console] = None,
    ) -> bool:
        """Remove a directory and all its contents.
        
        Args:
            dir_path: Directory to remove
            ui_enabled: Whether to show UI elements (status/messages)
            custom_console: Custom Rich console for output (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not dir_path.exists():
            return True
        
        _console = custom_console or console
        
        try:
            # Use status context only if UI is enabled
            status_ctx = _console.status(f"[cyan]Removing {dir_path}...") if ui_enabled else nullcontext()
            
            with status_ctx:
                shutil.rmtree(dir_path)
            
            if ui_enabled:
                _console.print(f"[green]✓ Removed {dir_path}")
            return True
        except Exception as e:
            if ui_enabled:
                _console.print(f"[red]Error removing {dir_path}: {e}")
            return False
