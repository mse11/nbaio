import click
import anyio
from pathlib import Path
from typing import Optional
from .util import AioUtils


@click.group()
@click.version_option()
def cli():
    "Simple async helper with IU support"


@cli.command(name="download")
@click.argument("urls", nargs=-1, required=True)
@click.option("-o", "--output", type=click.Path(path_type=Path), default=".", help="Output directory")
@click.option("-c", "--concurrent", type=int, default=5, help="Maximum concurrent downloads")
def download(urls: list[str], output: Path, concurrent: int):
    """Download multiple files concurrently."""
    output.mkdir(parents=True, exist_ok=True)
    
    downloads = []
    for url in urls:
        # Simple filename extraction from URL
        filename = url.split("/")[-1] or "downloaded_file"
        downloads.append((url, output / filename))
    
    async def do_download():
        results = await AioUtils.download_files(downloads, max_concurrent=concurrent)
        success_count = sum(1 for r in results if r)
        click.echo(f"Downloaded {success_count}/{len(urls)} files.")

    anyio.run(do_download)


@cli.command(name="extract")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output directory")
@click.option("--remove", is_flag=False, help="Remove archive after extraction")
def extract(path: Path, output: Optional[Path], remove: bool):
    """Extract a ZIP or TAR archive."""
    if output is None:
        # Default to a directory with the same name as the archive (minus extension)
        # or just the parent directory. Let's use parent for simplicity or follow common patterns.
        output = path.parent

    path_str = str(path).lower()
    
    async def do_extract():
        success = False
        if path_str.endswith(".zip"):
            success = await AioUtils.extract_zip(path, output, remove_after=remove)
        elif (path_str.endswith(".tar") or 
              path_str.endswith(".tar.gz") or 
              path_str.endswith(".tgz") or 
              path_str.endswith(".tar.bz2") or 
              path_str.endswith(".tar.xz")):
            success = await AioUtils.extract_tar(path, output, remove_after=remove)
        else:
            click.secho(f"Error: Unsupported archive format for '{path.name}'", fg="red")
            return

        if not success:
            # Error messages are already printed by AioUtils if ui_enabled=True (default)
            pass

    anyio.run(do_extract)

