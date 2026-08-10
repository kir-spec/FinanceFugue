import os
import shutil
import zipfile
from PySide6.QtCore import QThread, Signal

class CopyWorkerThread(QThread):
    progress = Signal(int, int)  # current, total bytes copied (or files)
    finished_one = Signal(str, str, bool) # original_path, final_path, is_dir
    finished_all = Signal()
    error = Signal(str)

    def __init__(self, tasks, db_folder, order_id):
        super().__init__()
        # tasks is a list of tuples: (source_path, dest_folder_relative_path, is_dir)
        self.tasks = tasks
        self.db_folder = db_folder
        self.order_id = order_id
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            for i, task in enumerate(self.tasks):
                if self._is_cancelled:
                    break
                    
                src_path = task['path']
                is_dir = task['is_dir']
                
                # Determine target relative path
                files_folder_rel = os.path.join("attached_files", self.order_id)
                files_folder_abs = os.path.join(self.db_folder, files_folder_rel)
                os.makedirs(files_folder_abs, exist_ok=True)
                
                base_name = os.path.basename(src_path)
                new_path_abs = os.path.join(files_folder_abs, base_name)
                
                # Collision resolution
                counter = 1
                name, ext = os.path.splitext(base_name)
                while os.path.exists(new_path_abs):
                    new_path_abs = os.path.join(files_folder_abs, f"{name}_{counter}{ext}")
                    counter += 1
                
                # Calculate relative path to store in DB
                final_rel_path = os.path.join(files_folder_rel, os.path.basename(new_path_abs))
                
                if is_dir:
                    shutil.copytree(src_path, new_path_abs)
                else:
                    # Optional: read in chunks to emit progress bytes for huge files
                    # But for simplicity, we just copy using shutil.
                    # shutil.copy2 handles large files well but blocks.
                    shutil.copy2(src_path, new_path_abs)
                
                self.progress.emit(i + 1, len(self.tasks))
                self.finished_one.emit(src_path, final_rel_path.replace('\\', '/'), is_dir)
                
            self.finished_all.emit()
        except Exception as e:
            self.error.emit(str(e))


class ZipWorkerThread(QThread):
    progress = Signal(int, int) # current_file_index, total_files
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, files_info, output_zip):
        super().__init__()
        # files_info is list of dicts: {'abs_path': str, 'arcname': str}
        self.files_info = files_info
        self.output_zip = output_zip
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            total = len(self.files_info)
            with zipfile.ZipFile(self.output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
                for i, info in enumerate(self.files_info):
                    if self._is_cancelled:
                        break
                    
                    path = info['abs_path']
                    arcname = info['arcname']
                    
                    if os.path.isdir(path):
                        # Add directory tree
                        for root, _, files in os.walk(path):
                            for file in files:
                                if self._is_cancelled:
                                    break
                                file_path = os.path.join(root, file)
                                rel_path = os.path.relpath(file_path, os.path.dirname(path))
                                z.write(file_path, os.path.join(arcname, rel_path))
                    else:
                        z.write(path, arcname)
                        
                    self.progress.emit(i + 1, total)
                    
            if self._is_cancelled:
                # delete partial zip
                if os.path.exists(self.output_zip):
                    try:
                        os.remove(self.output_zip)
                    except OSError:
                        pass
            else:
                self.finished.emit(self.output_zip)
        except Exception as e:
            self.error.emit(str(e))
