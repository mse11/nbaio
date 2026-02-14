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
@click.option("--filter", type=click.Choice(['data', 'tar', 'fully_trusted']), default='data', help="Filter level for TAR extraction (default: data)")
def extract(path: Path, output: Optional[Path], remove: bool, filter: str):
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
            success = await AioUtils.extract_tar(path, output, remove_after=remove, filter=filter)
        else:
            click.secho(f"Error: Unsupported archive format for '{path.name}'", fg="red")
            return

        if not success:
            # Error messages are already printed by AioUtils if ui_enabled=True (default)
            pass

    anyio.run(do_extract)

@cli.command(name="shell")
@click.argument("commands", nargs=-1, required=True)
@click.option("-c", "--concurrent", type=int, default=5, help="Maximum concurrent commands")
@click.option("--cwd", type=click.Path(exists=True, path_type=Path), help="Working directory")
def shell(commands: list[str], concurrent: int, cwd: Optional[Path]):
    """Run multiple shell commands concurrently.
    
    Example: nbaio shell "echo hello" "ls -la"
    """
    print(commands)
    async def do_shell():
        results = await AioUtils.shell_cmds(
            commands,
            max_concurrent=concurrent,
            cwd=cwd,
            ui_enabled=True
        )
        success_count = sum(1 for r in results if r[0] == 0)
        click.echo(f"Finished {len(commands)} commands. {success_count} succeeded.")

    anyio.run(do_shell)


@cli.command(name="git_clone")
@click.argument("args", nargs=-1, required=True)
@click.option("-s", "--separator", default=",", help="Separator between URL and destination pairs")
@click.option("-c", "--concurrent", type=int, default=5, help="Maximum concurrent clones")
@click.option("--cwd", type=click.Path(exists=True, path_type=Path), help="Working directory")
def git_clone(args: list[str], separator: str, concurrent: int, cwd: Optional[Path]):
    """Run multiple git clone commands concurrently.
    
    Format: URL [DEST] [SEPARATOR URL [DEST] ...]
    Example: nbaio git_clone URL1 DEST1 , URL2 , URL3 DEST3
    """
    clone_pairs = []
    current_group = []
    
    def add_pair(group):
        if len(group) == 1:
            clone_pairs.append((group[0], ""))
        elif len(group) == 2:
            clone_pairs.append((group[0], group[1]))
        elif len(group) > 2:
            raise click.UsageError(f"Invalid group: {' '.join(group)}. Expected URL and optional DEST.")
        elif len(group) == 0:
            pass # Empty group between separators or at start/end

    try:
        for arg in args:
            if arg == separator:
                add_pair(current_group)
                current_group = []
            else:
                current_group.append(arg)
        add_pair(current_group)
    except click.UsageError as e:
        click.secho(str(e), fg="red")
        return

    if not clone_pairs:
        click.secho("Error: No valid URL/DEST pairs provided.", fg="red")
        return
        
    async def do_clone():
        results = await AioUtils.shell_cmds_git_clone(
            clone_pairs,
            max_concurrent=concurrent,
            cwd=cwd,
            ui_enabled=True
        )
        success_count = sum(1 for r in results if r[0] == 0)
        click.echo(f"Finished {len(clone_pairs)} clones. {success_count} succeeded.")

    anyio.run(do_clone)
