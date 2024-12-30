import os
import json
import pyzipper
from datetime import datetime
from neo3.wallet.account import Account


class Wallet:
    def __init__(self, vault_path, vault_password):
        """
        Initializes the Wallet class with the given vault path and password.
        The vault is expected to be an AES-encrypted ZIP.

        :param vault_path:      Path to the AES-encrypted ZIP for local wallets.
        :param vault_password:  Password (str or bytes) to unlock the vault.
        """
        self.vault_path = vault_path
        if isinstance(vault_password, str):
            self.vault_password = vault_password.encode()
        else:
            self.vault_password = vault_password

    def list_wallets(self):
        """
        List all wallets currently stored in the vault (files named Matrix_User_*.json).
        """
        try:
            with pyzipper.AESZipFile(self.vault_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.vault_password)
                return [
                    name for name in zf.namelist()
                    if name.startswith("Matrix_User_") and name.endswith(".json")
                ]
        except Exception as e:
            raise RuntimeError(f"Error listing wallets in vault: {e}")

    def get_next_wallet_number(self):
        """
        Determine the next wallet number based on existing wallet files.

        Scans through all 'Matrix_User_<N>.json', extracts the integer <N>,
        and returns highest + 1. If none exist, returns 1.
        """
        wallet_names = self.list_wallets()
        highest_number = 0
        for name in wallet_names:
            try:
                number_str = name.replace("Matrix_User_", "").replace(".json", "")
                number = int(number_str)
                if number > highest_number:
                    highest_number = number
            except ValueError:
                pass  # ignore any files not matching the pattern

        return highest_number + 1

    def create_wallet(self, passphrase):
        """
        Create a new wallet with the given passphrase and store it in the vault.

        The JSON structure matches typical Neo N3 wallet format, e.g.:

        {
          "name": "Matrix_User_1",
          "version": "1.0",
          "scrypt": { "n":16384, "r":8, "p":8 },
          "accounts": [
            {
              "address": "...",
              "label": "Matrix_User_1",
              "lock": false,
              "key": "...",
              "contract": {
                "script": "...",
                "parameters": [...],
                "deployed": false
              },
              "extra": null,
              "isDefault": true
            }
          ],
          "extra": null
        }
        """
        try:
            wallet_number = self.get_next_wallet_number()

            # Create a new NEO account using neo-mamba
            new_account = Account.create_new(password=passphrase)

            # Scrypt params typically used by N3 wallets
            scrypt_params = {
                "n": 16384,
                "r": 8,
                "p": 8
            }

            wallet_name = f"Matrix_User_{wallet_number}"
            wallet_file = f"{wallet_name}.json"

            # Build the JSON structure
            account_dict = {
                "address": new_account.address,
                "label": wallet_name,
                "lock": False,
                "key": new_account.encrypted_key.decode("utf-8"),
                "contract": {
                    "script": new_account.contract.script.hex() if new_account.contract else "",
                    "parameters": [{"name": "signature", "type": "Signature"}],
                    "deployed": False
                },
                "extra": None,
                "isDefault": True
            }

            wallet_data = {
                "name": wallet_name,
                "version": "1.0",
                "scrypt": scrypt_params,
                "accounts": [account_dict],
                "extra": None
            }

            # Write to the vault (append mode)
            self._write_to_vault(wallet_file, wallet_data)

            # Record the passphrase in a CSV
            self.record_passphrase(wallet_file, passphrase)

            return wallet_file
        except Exception as e:
            raise RuntimeError(f"Error creating wallet: {e}")

    def _write_to_vault(self, wallet_file, wallet_data):
        """
        Write the wallet data into the vault's AES-encrypted ZIP in append mode.
        """
        try:
            with pyzipper.AESZipFile(
                self.vault_path,
                mode='a',
                compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES
            ) as zf:
                zf.setpassword(self.vault_password)
                content = json.dumps(wallet_data)
                zf.writestr(wallet_file, content)
        except Exception as e:
            raise RuntimeError(f"Error writing to vault: {e}")

    def connect_morpheus_wallet(self, zip_path, password):
        """
        Connect to a Morpheus wallet by extracting it from another AES-zip.
        """
        try:
            with pyzipper.AESZipFile(zip_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password.encode() if isinstance(password, str) else password)
                wallet_files = [n for n in zf.namelist() if n.endswith(".json")]
                if len(wallet_files) != 1:
                    raise ValueError("Morpheus ZIP must contain exactly one .json wallet file.")

                content = zf.read(wallet_files[0]).decode("utf-8")
                wallet_data = json.loads(content)
                if not isinstance(wallet_data, dict) or "accounts" not in wallet_data:
                    raise ValueError("Invalid wallet data structure. No 'accounts' field.")

                accounts = wallet_data["accounts"]
                if not accounts or "address" not in accounts[0]:
                    raise ValueError("Public address not found in the Morpheus wallet data.")

                public_address = accounts[0]["address"]
                return public_address, wallet_data
        except Exception as e:
            raise RuntimeError(f"Error connecting to Morpheus wallet: {e}")

    def record_passphrase(self, wallet_name, passphrase):
        """
        Record the passphrase for the wallet in a CSV file: F:/KeyMaker/keys.csv
        """
        keys_file = "F:/KeyMaker/keys.csv"
        try:
            os.makedirs(os.path.dirname(keys_file), exist_ok=True)
            with open(keys_file, "a", encoding="utf-8") as f:
                creation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{wallet_name},{creation_time},{passphrase}\n")
        except PermissionError:
            raise RuntimeError(f"Permission issue: Unable to write to {keys_file}. Check file permissions.")
        except Exception as e:
            raise RuntimeError(f"Error recording passphrase: {e}")
