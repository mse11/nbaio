from click.testing import CliRunner
from nbaio.cli import cli


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
