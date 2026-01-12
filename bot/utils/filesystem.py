import os


def list_folders(path: str):
    """List folders in the given path."""
    if not os.path.exists(path):
        os.makedirs(path)
    return [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]

def get_available_folders(path: str) -> list:
    """Get list of available folders for selection."""
    return list_folders(path)

def create_folder(path: str):
    """Create a folder if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
    elif not os.path.isdir(path):
        raise Exception(f"{path} существует, но не является папкой.")

def rename_file(old_path: str, new_path: str):
    """Rename a file."""
    if not os.path.exists(old_path):
        raise Exception(f"Файл не найден: {old_path}")
    if os.path.exists(new_path):
        raise Exception(f"Файл уже существует: {new_path}")
    os.rename(old_path, new_path)