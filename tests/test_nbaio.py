from unittest.mock import AsyncMock, patch
from click.testing import CliRunner
from nbaio.cli import cli
from nbaio.util import AioUtils


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("cli, version ")


def test_extract_zip_cli():
    import zipfile
    from pathlib import Path
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a test zip file
        zip_path = Path("test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.txt", "hello world")
        
        # Run the extract command
        result = runner.invoke(cli, ["extract", str(zip_path)])
        
        assert result.exit_code == 0
        assert Path("test.txt").exists()
        assert Path("test.txt").read_text() == "hello world"


def test_download_cli():
    import respx
    import httpx
    from pathlib import Path
    runner = CliRunner()
    
    url1 = "https://example.com/file1.txt"
    url2 = "https://example.com/file2.txt"
    
    with respx.mock:
        respx.get(url1).mock(return_value=httpx.Response(200, content=b"content1"))
        respx.get(url2).mock(return_value=httpx.Response(200, content=b"content2"))
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["download", url1, url2])
            
            assert result.exit_code == 0
            assert "Downloaded 2/2 files" in result.output
            assert Path("file1.txt").read_text() == "content1"
            assert Path("file2.txt").read_text() == "content2"


def test_shell_cli():
    runner = CliRunner()
    result = runner.invoke(cli, ["shell", "echo hello", "echo world"])
    
    assert result.exit_code == 0
    assert "Finished 2 commands. 2 succeeded." in result.output


def test_git_clone_cli():
    runner = CliRunner()
    
    # Mock AioUtils.shell_cmds_git_clone
    with patch.object(AioUtils, 'shell_cmds_git_clone', new_callable=AsyncMock) as mock_clone:
        mock_clone.return_value = [(0, "", "")]
        
        # Test 1: Simple pair
        result = runner.invoke(cli, ["git_clone", "URL1", "DEST1"])
        print(f"Test 1 (Simple pair) Output: {result.output}")
        mock_clone.assert_called_with([("URL1", "DEST1")], max_concurrent=5, cwd=None, ui_enabled=True)
        
        # Test 2: URL without DEST
        result = runner.invoke(cli, ["git_clone", "URL2"])
        print(f"Test 2 (URL without DEST) Output: {result.output}")
        mock_clone.assert_called_with([("URL2", "")], max_concurrent=5, cwd=None, ui_enabled=True)
        
        # Test 3: Multiple pairs with separator
        result = runner.invoke(cli, ["git_clone", "URL3", "DEST3", ",", "URL4"])
        print(f"Test 3 (Multiple pairs) Output: {result.output}")
        mock_clone.assert_called_with([("URL3", "DEST3"), ("URL4", "")], max_concurrent=5, cwd=None, ui_enabled=True)

        # Test 4: Custom separator
        result = runner.invoke(cli, ["git_clone", "-s", "|", "URL5", "|", "URL6", "DEST6"])
        print(f"Test 4 (Custom separator) Output: {result.output}")
        mock_clone.assert_called_with([("URL5", ""), ("URL6", "DEST6")], max_concurrent=5, cwd=None, ui_enabled=True)

        # Test 5: Error case (too many args in a group)
        result = runner.invoke(cli, ["git_clone", "URL7", "DEST7", "EXTRA"])
        print(f"Test 5 (Error case) Output: {result.output}")
        assert "Invalid group" in result.output
