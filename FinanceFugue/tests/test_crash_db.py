import pytest
import json
from src.storage import CRMStorage, DatabaseLoadError
from src.models import Client

def test_db_corrupted_json(tmp_path):
    """Test loading a corrupted JSON file raises DatabaseLoadError."""
    db_file = tmp_path / "pro_database.json"
    db_file.write_text("{ this is not json ]", encoding="utf-8")
    
    storage = CRMStorage(str(db_file))
    with pytest.raises(DatabaseLoadError):
        storage.load()

def test_db_missing_required_fields(tmp_path):
    """Test loading JSON with missing fields raises DatabaseLoadError."""
    db_file = tmp_path / "pro_database.json"
    data = {"schema_version": 1, "clients": [{"email": "test@test.com"}]} # missing id and name
    db_file.write_text(json.dumps(data), encoding="utf-8")
    
    storage = CRMStorage(str(db_file))
    with pytest.raises(DatabaseLoadError):
        storage.load()

def test_db_permission_error_on_save(tmp_path, monkeypatch):
    """Test saving when a PermissionError occurs."""
    db_file = tmp_path / "pro_database.json"
    storage = CRMStorage(str(db_file))
    
    # Create valid client
    client = Client(id="1", name="Test", orders=[])
    
    # Mock open to raise PermissionError
    def mock_open(*args, **kwargs):
        raise PermissionError("Permission denied")
        
    monkeypatch.setattr("builtins.open", mock_open)
    
    with pytest.raises(PermissionError):
        storage.save([client])

def test_db_save_preserves_old_file_on_error(tmp_path):
    """Test that an error during serialization doesn't corrupt the existing database file."""
    db_file = tmp_path / "pro_database.json"
    valid_data = {"schema_version": 1, "clients": [{"id": "1", "name": "Valid", "orders": []}]}
    db_file.write_text(json.dumps(valid_data), encoding="utf-8")
    
    storage = CRMStorage(str(db_file))
    clients = storage.load()
    
    # Introduce an error by creating a client that will fail serialization (e.g. non-serializable object)
    class Unserializable:
        pass
        
    bad_client = Client(id="2", name="Bad", orders=[])
    bad_client.name = Unserializable() # type: ignore
    
    clients.append(bad_client)
    
    with pytest.raises(Exception):
        storage.save(clients)
        
    # The original file should be completely intact
    assert db_file.exists()
    assert "Valid" in db_file.read_text(encoding="utf-8")
    assert not db_file.with_suffix(".tmp").exists()
