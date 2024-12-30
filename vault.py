import pyzipper


class Vault:
    def __init__(self):
        self.path = None
        self.password = None

    def set_vault(self, path, password):
        """Set vault details."""
        self.path = path
        self.password = password.encode() if isinstance(password, str) else password

    def create_vault(self):
        """Create an encrypted vault."""
        if not self.path or not self.password:
            raise ValueError("Vault path and password must be set.")
        try:
            with pyzipper.AESZipFile(self.path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.password)
                zf.writestr("vault_initialized.txt", "Vault is encrypted and ready.")
        except Exception as e:
            raise RuntimeError(f"Error creating vault: {e}")

    def validate_vault(self):
        """Validate the vault password."""
        if not self.path or not self.password:
            raise ValueError("Vault path and password must be set.")
        try:
            with pyzipper.AESZipFile(self.path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.password)
                content = zf.read("vault_initialized.txt").decode("utf-8")
                return True
        except pyzipper.zipfile.BadZipFile:
            raise RuntimeError("Invalid or corrupted ZIP file. Please create a new vault.")
        except Exception as e:
            raise RuntimeError(f"Error validating vault: {e}")

    def list_vault_contents(self):
        """List the contents of the vault."""
        if not self.path or not self.password:
            raise ValueError("Vault path and password must be set.")
        try:
            with pyzipper.AESZipFile(self.path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.password)
                return zf.namelist()
        except Exception as e:
            raise RuntimeError(f"Error reading vault contents: {e}")

    def write_to_vault(self, file_name, file_data):
        """Write a file to the vault."""
        if not self.path or not self.password:
            raise ValueError("Vault path and password must be set.")
        retries = 3
        while retries > 0:
            try:
                with pyzipper.AESZipFile(self.path, 'a', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(self.password)
                    if file_name in zf.namelist():
                        raise RuntimeError(f"Duplicate file name: {file_name}")
                    zf.writestr(file_name, file_data)
                return
            except RuntimeError as e:
                retries -= 1
                if retries == 0:
                    raise RuntimeError(f"Failed to write to vault after 3 attempts: {e}")
            except Exception as e:
                raise RuntimeError(f"Unexpected error during write: {e}")

    def extract_file(self, file_name):
        """Extract a specific file from the vault."""
        if not self.path or not self.password:
            raise ValueError("Vault path and password must be set.")
        try:
            with pyzipper.AESZipFile(self.path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.password)
                return zf.read(file_name).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Error extracting file {file_name}: {e}")
