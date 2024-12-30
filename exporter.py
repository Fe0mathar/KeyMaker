import pyzipper
import json

class WalletExporter:
    """
    Handles exporting public addresses from the vault (ZIP) to a specified file.
    Uses AES encryption for reading the vault data.
    """
    def __init__(self, vault_path, password):
        """
        :param vault_path:  Path to the vault (.zip).
        :param password:    Vault password (string or bytes).
        """
        self.vault_path = vault_path
        if isinstance(password, bytes):
            self.password = password
        else:
            self.password = password.encode()

    def export_addresses(self, output_file, progress_callback=None):
        """
        Export public addresses from all wallet .json files inside the vault
        to a specified output text file.

        :param output_file:       Path to the output .txt file.
        :param progress_callback: Optional function to report progress (int 0..100).
        :raises RuntimeError:     On any error reading from the vault or writing to file.
        """
        try:
            with pyzipper.AESZipFile(self.vault_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.password)
                wallet_files = [name for name in zf.namelist() if name.endswith('.json')]
                if not wallet_files:
                    raise RuntimeError("No wallet files found in the vault.")

                with open(output_file, 'w', encoding='utf-8') as file:
                    total_files = len(wallet_files)
                    for i, wallet_name in enumerate(wallet_files):
                        raw_json = zf.read(wallet_name).decode('utf-8')
                        wallet_data = json.loads(raw_json)
                        public_address = (
                            wallet_data.get('accounts', [{}])[0]
                            .get('address', 'Unknown Address')
                        )
                        file.write(f"{wallet_name}: {public_address}\n")

                        if progress_callback:
                            percent = int(((i + 1) / total_files) * 100)
                            progress_callback(percent)

        except Exception as e:
            raise RuntimeError(f"Error exporting addresses: {e}")
