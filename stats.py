import pyzipper
from datetime import datetime
from collections import defaultdict
import random

class StatsManager:
    """
    StatsManager handles extraction of wallet creation data and other 
    statistics from an AES-encrypted vault (ZIP). 
    Provides data for generating charts/diagrams in KeyMakerApp.
    """
    def __init__(self, vault_path, password):
        """
        :param vault_path:  The path to the vault .zip file.
        :param password:    The vault password (string or bytes).
        """
        self.vault_path = vault_path
        if isinstance(password, str):
            self.password = password.encode()
        else:
            self.password = password

    def get_wallet_transactions(self):
        """
        Mock data for a donut/pie chart of transactions.

        :return: A list representing [Inbound, Outbound, Pending] transaction counts.
        """
        # In real usage, you'd parse actual transaction logs or metadata from the vault.
        return [40, 30, 30]

    def get_network_activity(self):
        """
        Mock data for a donut/pie chart of network activity.

        :return: A list representing [Blocks Mined, Transactions, Gas Fees].
        """
        # Similarly, you'd parse actual on-chain data or logs for real usage.
        return [50, 30, 20]

    def get_wallet_volume_trend(self):
        """
        Extract wallet creation dates (X-axis) and volume for each date, 
        returning two sub-volumes: 'full' and 'empty' counts.

        We treat each .json in the vault zip as a distinct "wallet file."
        We retrieve its creation date from the ZIP info date_time.

        :return: (sorted_dates, full_counts, empty_counts)

          - sorted_dates: list of date strings "YYYY-MM-DD"
          - full_counts: random-split int volumes for 'full' wallets
          - empty_counts: complement of full_counts
        """
        try:
            wallet_counts = defaultdict(int)

            with pyzipper.AESZipFile(self.vault_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.password)
                for name in zf.namelist():
                    if name.endswith(".json"):
                        info = zf.getinfo(name)
                        creation_date = datetime(*info.date_time).strftime("%Y-%m-%d")
                        wallet_counts[creation_date] += 1

            # Sort by date
            sorted_dates = sorted(wallet_counts.keys())
            volumes = [wallet_counts[date] for date in sorted_dates]

            # Randomly split each day's volume into 'full' vs 'empty'
            full_counts = [random.randint(0, vol) for vol in volumes]
            empty_counts = [vol - full for vol, full in zip(volumes, full_counts)]

            return sorted_dates, full_counts, empty_counts

        except Exception as e:
            print(f"[StatsManager] Error fetching wallet volume trend: {e}")
            return [], [], []
