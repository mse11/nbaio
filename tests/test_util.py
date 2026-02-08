import pytest
import httpx
import respx
import zipfile
import tarfile
from nbaio.util import AioUtils

#==========================================================================
# FIXTURES
#==========================================================================
@pytest.fixture
def temp_dir(tmp_path):
    """Fixture to provide a clean temporary directory."""
    return tmp_path

@pytest.fixture
def mock_download_url():
    return "https://example.com/test.txt"

@pytest.fixture
def mock_download_content():
    return b"Hello world"

#==========================================================================
# TESTS
#==========================================================================

def test_check_file_size(temp_dir):
    file_path = temp_dir / "test.txt"
    content = b"12345"
    file_path.write_bytes(content)
    
    # Exact match
    assert AioUtils.check_file_size(file_path, 5) is True
    # Within tolerance (1%)
    assert AioUtils.check_file_size(file_path, 5, tolerance=0.1) is True
    # Outside tolerance
    assert AioUtils.check_file_size(file_path, 10, tolerance=0.1) is False
    # Non-existent file
    assert AioUtils.check_file_size(temp_dir / "nope.txt", 5) is False

def test_remove_directory(temp_dir):
    nested_dir = temp_dir / "nested" / "dir"
    nested_dir.mkdir(parents=True)
    test_file = nested_dir / "test.txt"
    test_file.write_text("content")
    
    assert nested_dir.exists()
    assert AioUtils.remove_directory(temp_dir / "nested", ui_enabled=False) is True
    assert not (temp_dir / "nested").exists()
    
    # Handle non-existent
    assert AioUtils.remove_directory(temp_dir / "not_here", ui_enabled=False) is True

@pytest.mark.anyio
async def test_shell_command():
    # Simple success command
    exit_code, stdout, stderr = await AioUtils.shell_command(["echo", "hello"], capture_output=True, ui_enabled=False)
    assert exit_code == 0
    assert stdout.strip() == "hello"
    assert stderr == ""
    
    # Error command
    # Windows doesn't always have 'ls' or 'false', using a Python script as cross-platform "fail"
    exit_code, stdout, stderr = await AioUtils.shell_command(["python", "-c", "import sys; sys.exit(1)"], capture_output=True, ui_enabled=False)
    assert exit_code == 1

@pytest.mark.anyio
async def test_shell_commands():
    commands = [
        "echo one",
        "echo two ; echo three",
        ["python", "-c", "import sys; sys.exit(1)"]
    ]
    results = await AioUtils.shell_commands(commands, capture_output=True, ui_enabled=False)
    
    assert len(results) == 3
    assert results[0][0] == 0
    assert results[1][0] == 0
    assert results[2][0] == 1
    assert results[0][1].strip() == "one"
    # The result of "echo two ; echo three" should contain both
    assert "two" in results[1][1]
    assert "three" in results[1][1]

@pytest.mark.anyio
async def test_download_file(temp_dir, mock_download_url, mock_download_content):
    dest_path = temp_dir / "downloaded.txt"
    
    with respx.mock:
        respx.get(mock_download_url).mock(return_value=httpx.Response(200, content=mock_download_content))
        
        success = await AioUtils.download_file(
            mock_download_url,
            dest_path,
            ui_enabled=False
        )
        
        assert success is True
        assert dest_path.exists()
        assert dest_path.read_bytes() == mock_download_content

@pytest.mark.anyio
async def test_download_files(temp_dir, mock_download_url, mock_download_content):
    dest1 = temp_dir / "file1.txt"
    dest2 = temp_dir / "file2.txt"
    downloads = [(mock_download_url, dest1), (mock_download_url, dest2)]
    
    with respx.mock:
        respx.get(mock_download_url).mock(return_value=httpx.Response(200, content=mock_download_content))
        
        results = await AioUtils.download_files(downloads, ui_enabled=False)
        
        assert len(results) == 2
        assert all(results)
        assert dest1.read_bytes() == mock_download_content
        assert dest2.read_bytes() == mock_download_content

@pytest.mark.anyio
async def test_extract_zip(temp_dir):
    zip_path = temp_dir / "test.zip"
    extract_to = temp_dir / "extracted_zip"
    content = {"file1.txt": "hello", "sub/file2.txt": "world"}
    
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in content.items():
            zf.writestr(name, data)
    
    success = await AioUtils.extract_zip(zip_path, extract_to, remove_after=False, ui_enabled=False)
    
    assert success is True
    assert (extract_to / "file1.txt").read_text() == "hello"
    assert (extract_to / "sub" / "file2.txt").read_text() == "world"

@pytest.mark.anyio
async def test_extract_tar(temp_dir):
    tar_path = temp_dir / "test.tar.gz"
    extract_to = temp_dir / "extracted_tar"
    content = {"file1.txt": "hello content"}
    
    with tarfile.open(tar_path, "w:gz") as tf:
        for name, data in content.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            import io
            tf.addfile(info, io.BytesIO(data.encode()))
            
    success = await AioUtils.extract_tar(tar_path, extract_to, remove_after=False, ui_enabled=False)
    
    assert success is True
    assert (extract_to / "file1.txt").read_text() == "hello content"
