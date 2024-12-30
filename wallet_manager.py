import os
import json
import pyzipper
import time
import threading
from datetime import datetime

# For Morpheus connectivity (optional local references)
from neo3.wallet.account import Account


class WalletManager:
    def __init__(self, vault_path, vault_password, neo_cli_manager, console_window=None):
        """
        Manages Morpheus wallet connectivity within an AES-encrypted vault,
        plus an optional demonstration method for multi-wallet creation.

        :param vault_path:      Path to the AES-encrypted vault (.zip).
        :param vault_password:  Password (str or bytes) for the vault.
        :param neo_cli_manager: Manages the Neo-CLI process/commands.
        :param console_window:  Reference to ConsoleWindow for logging (if any).
        """
        self.vault_path = vault_path
        if isinstance(vault_password, str):
            self.vault_password = vault_password.encode()
        else:
            self.vault_password = vault_password

        self.neo_cli_manager = neo_cli_manager
        self.console_window = console_window

        # Track local .json wallets
        self.wallet_count = 0
        self.morpheus_wallet = None
        self.morpheus_wallet_path = None

        # Initialize the local wallet count
        self.update_wallet_count()

    def _log(self, message, color=None):
        """
        Helper to log to console_window if available, else print.
        Default color => "#00FF00" for operator logs.
        """
        if self.console_window:
            self.console_window.log(message, tag="operator", color=color or "#00FF00")
        else:
            print(f"[WalletManager] {message}")

    def update_wallet_count(self):
        """
        Count how many "Matrix_User_*.json" files are in vault_path
        for reference if needed.
        """
        try:
            with pyzipper.AESZipFile(self.vault_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.vault_password)
                self.wallet_count = sum(
                    1
                    for name in zf.namelist()
                    if name.startswith("Matrix_User_") and name.endswith(".json")
                )
        except Exception as e:
            raise RuntimeError(f"Error reading vault: {e}")

    # --------------------------------------------------------------------------
    # Morpheus Wallet Connection
    # --------------------------------------------------------------------------
    def connect_morpheus_wallet(self, zip_path, password, update_gui_callback=None):
        """
        Decrypt & load a Morpheus wallet from a separate AES-encrypted ZIP,
        ensure Neo-CLI is running, then 'open wallet <temp_wallet_path>'.
        The console sees "OPERATOR: Provide Password." => triggers pass flow.

        :param zip_path: Path to the Morpheus ZIP (with exactly 1 .json).
        :param password: WZ_AES password (str or bytes).
        :param update_gui_callback: If provided, called with partial wallet_data dict
                                    e.g. {"public_address":..., "gas_balance":"N/A"}.
        :return: The same partial wallet_data dict.
        """
        if not self.console_window:
            raise RuntimeError("No ConsoleWindow in WalletManager for logging Morpheus actions.")

        try:
            with pyzipper.AESZipFile(zip_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password.encode() if isinstance(password, str) else password)
                wallet_files = [f for f in zf.namelist() if f.endswith(".json")]

                if len(wallet_files) != 1:
                    raise ValueError("Morpheus ZIP must contain exactly one .json wallet file.")

                # Extract .json to a temp directory
                temp_dir = os.environ.get("TEMP", os.getcwd())
                temp_wallet_path = os.path.join(temp_dir, wallet_files[0])
                with open(temp_wallet_path, "wb") as tmp_file:
                    tmp_file.write(zf.read(wallet_files[0]))

                # Load partial data
                with open(temp_wallet_path, "r", encoding="utf-8") as f:
                    self.morpheus_wallet = json.load(f)
                self.morpheus_wallet_path = temp_wallet_path

            # Ensure Neo-CLI is running
            if not self.neo_cli_manager.is_running():
                self._log("OPERATOR: Starting Neo-CLI for fresh Morpheus connection...", color="#00FF00")
                self.neo_cli_manager.start_cli()

            # open wallet <temp_wallet_path>
            self._log("OPERATOR: Connecting wallet to Neo-CLI...", color="#00FF00")
            self.neo_cli_manager.connect_wallet(temp_wallet_path)

            # console sees "OPERATOR: Provide Password."
            self._log("OPERATOR: Provide Password.")

            # partial data for GUI
            wallet_data = {
                "public_address": self.morpheus_wallet["accounts"][0]["address"],
                "gas_balance": "N/A"
            }
            if update_gui_callback:
                update_gui_callback(wallet_data)

            return wallet_data

        except Exception as e:
            self._log("OPERATOR: An error occurred while connecting Morpheus wallet.", color="#FF0000")
            raise RuntimeError(f"Error connecting to Morpheus wallet: {e}")

    # --------------------------------------------------------------------------
    # Multi-Wallet Creation (Placeholder / Demo)
    # --------------------------------------------------------------------------
    def create_multiple_wallets(self, count, passphrase_callback=None, progress_callback=None):
        """
        A placeholder/demo method for multi-wallet creation.
        In your real code, local wallet creation is done by console.py & wallet.py.

        :param count: how many wallets to simulate
        :param passphrase_callback: function returning a pass (if any)
        :param progress_callback: function accepting int percent
        """
        try:
            if count <= 0:
                raise ValueError("Wallet count must be a positive integer.")

            for i in range(count):
                passphrase = passphrase_callback() if passphrase_callback else "default-pass"
                time.sleep(0.3)  # or remove the sleep
                pct = int((i + 1) / count * 100)
                if progress_callback:
                    progress_callback(pct)

            # re-check wallet count if you appended any .json
            self.update_wallet_count()

        except Exception as e:
            raise RuntimeError(f"Error in create_multiple_wallets: {e}")

    # --------------------------------------------------------------------------
    # Optional passphrase recording
    # --------------------------------------------------------------------------
    def record_passphrase(self, wallet_name, passphrase):
        """
        If you'd like to record passphrases in F:/KeyMaker/keys.csv 
        after connecting Morpheus or local creation.
        """
        keys_file = "F:/KeyMaker/keys.csv"
        try:
            os.makedirs(os.path.dirname(keys_file), exist_ok=True)
            with open(keys_file, "a", encoding="utf-8") as f:
                creation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{wallet_name},{creation_time},{passphrase}\n")
        except PermissionError:
            raise RuntimeError(f"Permission issue: Unable to write to {keys_file}.")
        except Exception as e:
            raise RuntimeError(f"Error recording passphrase: {e}")
