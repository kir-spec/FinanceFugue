from src.utils.file_worker import CopyWorkerThread

def test_copy_worker_resolves_relative_paths(tmp_path):
    """Test that CopyWorkerThread creates correct relative paths."""
    # Create mock file
    src_file = tmp_path / "source.txt"
    src_file.write_text("hello", encoding="utf-8")
    
    # Db folder
    db_folder = tmp_path / "db"
    db_folder.mkdir()
    
    tasks = [
        {'path': str(src_file), 'is_dir': False}
    ]
    
    worker = CopyWorkerThread(tasks, str(db_folder), "order123")
    
    # Capture emitted signals
    results = []
    worker.finished_one.connect(lambda orig, final, is_dir: results.append(final))
    
    worker.run()
    
    assert len(results) == 1
    # Check that it stored a relative path properly
    assert results[0] == "attached_files/order123/source.txt"
    
    # Check physical file exists
    assert (db_folder / "attached_files" / "order123" / "source.txt").exists()

def test_copy_worker_collision(tmp_path):
    """Test collision renaming."""
    src_file = tmp_path / "video.mp4"
    src_file.write_text("video", encoding="utf-8")
    
    db_folder = tmp_path / "db"
    dest_dir = db_folder / "attached_files" / "order123"
    dest_dir.mkdir(parents=True)
    
    # Pre-create the file to force collision
    (dest_dir / "video.mp4").write_text("old_video", encoding="utf-8")
    
    tasks = [{'path': str(src_file), 'is_dir': False}]
    worker = CopyWorkerThread(tasks, str(db_folder), "order123")
    
    results = []
    worker.finished_one.connect(lambda orig, final, is_dir: results.append(final))
    
    worker.run()
    
    assert results[0] == "attached_files/order123/video_1.mp4"
    assert (dest_dir / "video_1.mp4").exists()
