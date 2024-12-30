import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
from tkinter.ttk import Progressbar
from neo3.wallet.wallet import Wallet, DiskWallet


# ------------------------------
# Wallet Functions Module
# ------------------------------

def create_wallet(wallet_number: int, directory: str = "wallets"):
    """Creates a new wallet and saves it in the specified directory with the appropriate name."""
    if not os.path.exists(directory):
        os.makedirs(directory)

    wallet = Wallet()
    # Provide empty string as password to avoid prompting for one
    new_account = wallet.account_new(password="", label=f"Matrix_User_{wallet_number}")  # No password required
    
    wallet_path = os.path.join(directory, f"Matrix_User_{wallet_number}.json")
    
    while os.path.exists(wallet_path):
        wallet_number += 1
        wallet_path = os.path.join(directory, f"Matrix_User_{wallet_number}.json")
    
    wallet.save()  # Save the wallet
    
    return wallet

def create_wallet_and_save(wallet_number: int, directory: str = "wallets"):
    """Creates a new wallet and saves it to a JSON file in the specified directory."""
    if not os.path.exists(directory):
        os.makedirs(directory)

    wallet_path = os.path.join(directory, f"Matrix_User_{wallet_number}.json")
    
    while os.path.exists(wallet_path):
        wallet_number += 1
        wallet_path = os.path.join(directory, f"Matrix_User_{wallet_number}.json")

    wallet = DiskWallet.default(path=wallet_path)
    # Provide empty string as password to avoid prompting for one
    new_account = wallet.account_new(password="", label=f"Matrix_User_{wallet_number}")  # No password required
    wallet.save()

    return wallet

def create_multiple_wallets(count: int, directory: str = "wallets", progress_bar=None, progress_label=None):
    """Creates multiple wallets in the specified directory and updates the progress bar with percentage."""
    for i in range(count):
        create_wallet_and_save(i, directory)
        if progress_bar:
            fraction = (i + 1) / count * 100
            progress_bar['value'] = fraction
            progress_label.config(text=f"{int(fraction)}%")  # Update percentage label
            progress_bar.update()

    # Action completion message with a summary (Only one popup)
    messagebox.showinfo("Wake up NEO", f"Successfully created {count} wallets!")


def list_wallets(directory: str = "wallets") -> list:
    """Lists all wallets in the specified directory."""
    return os.listdir(directory)

def get_wallet_count(directory: str = "wallets") -> int:
    """Returns the number of wallets in the specified directory."""
    return len(list_wallets(directory))

def export_public_addresses(directory: str = "wallets", output_file: str = "public_addresses.txt"):
    """Exports public addresses from all wallets into a .txt file."""
    wallet_files = list_wallets(directory)
    with open(output_file, "w") as file:
        for wallet_file in wallet_files:
            if wallet_file.endswith(".json"):
                wallet_path = os.path.join(directory, wallet_file)
                wallet = DiskWallet.from_file(wallet_path)
                public_address = wallet.account_default.address
                file.write(f"{public_address}\n")
    return output_file


# ------------------------------
# Morpheus Wallet Module
# ------------------------------

class MorpheusWallet:
    def __init__(self, wallet_file: str = "Morpheus_wallet.json"):
        self.wallet_file = wallet_file
        self.wallet = None
        self.account = None
        self.gas_balance = 100  # Placeholder for gas balance

    def create_new_wallet(self, directory: str = "wallets"):
        """Create a new Morpheus wallet and save it to the specified directory."""
        self.wallet = Wallet()
        self.account = self.wallet.account_new(password="", label="Morpheus_Master")  # No password required
        self.save_wallet(directory)

    def load_wallet(self, directory: str = "wallets"):
        """Load an existing Morpheus wallet by selecting the directory."""
        if os.path.exists(self.wallet_file):
            self.wallet = DiskWallet.from_file(self.wallet_file)  # Use DiskWallet to load
            self.account = self.wallet.accounts[0]  # Load the first account as the master
            print(f"Loaded Morpheus wallet with address: {self.account.address}")
        else:
            raise FileNotFoundError("Morpheus wallet file does not exist.")

    def save_wallet(self, directory: str = "wallets"):
        """Save the Morpheus wallet to a file."""
        wallet_path = os.path.join(directory, self.wallet_file)
        disk_wallet = DiskWallet.default(path=wallet_path)  # Create a DiskWallet
        disk_wallet.save()  # Save it using DiskWallet's save method
        print(f"Morpheus wallet saved at {wallet_path}")

    def get_gas_balance(self):
        """Get the gas balance of the Morpheus wallet."""
        return self.gas_balance


# ------------------------------
# GUI Module
# ------------------------------

class KeyMakerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KeyMaker Application")
        self.root.geometry("600x400")  # Wider window to display full address
        
        # Set background color of the window
        self.root.configure(bg="#20242B")
        
        # Default directories
        self.wallets_directory = "wallets"
        self.output_directory = os.getcwd()  # Current working directory
        
        # Morpheus wallet
        self.morpheus_wallet = MorpheusWallet()
        
        # Labels with custom colors
        self.wallet_address_label = tk.Label(root, text="Wallet Not Connected", font=("Arial", 14), fg="#20E8AA", bg="white", anchor="w")
        self.wallet_address_label.pack(pady=10, padx=20, fill="x")

        self.wallet_count = get_wallet_count(self.wallets_directory)
        
        # Label to show number of wallets
        self.wallet_count_label = tk.Label(root, text=f"Current number of wallets: {self.wallet_count}", fg="#20E8AA", bg="#15191F")
        self.wallet_count_label.pack(pady=10)

        # Label to display gas balance of Morpheus
        self.gas_balance_label = tk.Label(root, text="Gas Balance: Not Connected", font=("Arial", 12), fg="#20E8AA", bg="#15191F")
        self.gas_balance_label.pack(pady=10)

        # Button to create wallets
        self.create_wallet_button = tk.Button(root, text="Create Wallets", command=self.create_wallets, bg="#20242B", fg="#20E8AA", relief="flat", borderwidth=0)
        self.create_wallet_button.pack(pady=10)

        # Button to export public addresses
        self.export_button = tk.Button(root, text="Export Public Addresses", command=self.export_addresses, bg="#20242B", fg="#20E8AA", relief="flat", borderwidth=0)
        self.export_button.pack(pady=10)

        # Button to connect Morpheus wallet
        self.connect_morpheus_button = tk.Button(root, text="Connect Morpheus Wallet", command=self.connect_morpheus_wallet, bg="#20242B", fg="#20E8AA", relief="flat", borderwidth=0)
        self.connect_morpheus_button.pack(pady=10)

        # Button to create Morpheus wallet
        self.create_morpheus_button = tk.Button(root, text="Create Morpheus Wallet", command=self.create_morpheus_wallet, bg="#20242B", fg="#20E8AA", relief="flat", borderwidth=0)
        self.create_morpheus_button.pack(pady=10)

        # Progress bar
        self.progress_bar = Progressbar(root, length=200, mode='determinate')
        self.progress_bar.pack(pady=10)

        # Label to show percentage in progress bar
        self.progress_percentage_label = tk.Label(root, text="0%", font=("Arial", 10), fg="#20E8AA", bg="#15191F")
        self.progress_percentage_label.pack()

        # Button to specify wallet directory
        self.set_wallet_dir_button = tk.Button(root, text="Set Wallet Directory", command=self.set_wallet_directory, bg="#20242B", fg="#20E8AA", relief="flat", borderwidth=0)
        self.set_wallet_dir_button.pack(pady=10)

        # Button to exit
        self.exit_button = tk.Button(root, text="Exit", command=root.quit, bg="#20242B", fg="#20E8AA", relief="flat", borderwidth=0)
        self.exit_button.pack(pady=10)

    def create_wallets(self):
        count = tk.simpledialog.askinteger("Input", "How many wallets do you want to create?", minvalue=1, maxvalue=100000)
        if count:
            self.progress_bar['maximum'] = count
            create_multiple_wallets(count, self.wallets_directory, self.progress_bar, self.progress_percentage_label)
            self.wallet_count = get_wallet_count(self.wallets_directory)  # Update wallet count
            self.wallet_count_label.config(text=f"Current number of wallets: {self.wallet_count}")
            messagebox.showinfo("Wake up NEO", f"Successfully created {count} wallets!")

    def export_addresses(self):
        output_directory = filedialog.askdirectory(initialdir=self.output_directory, title="Select Directory to Save Output")
        if output_directory:
            output_file = os.path.join(output_directory, "public_addresses.txt")
            try:
                export_public_addresses(self.wallets_directory, output_file)
                messagebox.showinfo("Success", f"Public addresses have been exported to {output_file}")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred: {e}")

    def connect_morpheus_wallet(self):
        # User will select directory to load the Morpheus wallet
        wallet_file = filedialog.askopenfilename(title="Select Morpheus Wallet File", filetypes=[("JSON Files", "*.json")])
        if wallet_file:
            self.morpheus_wallet.wallet_file = wallet_file
            try:
                self.morpheus_wallet.load_wallet()
                self.wallet_address_label.config(text=f"Morpheus Wallet Address: {self.morpheus_wallet.account.address}")
                self.gas_balance_label.config(text=f"Gas Balance: {self.morpheus_wallet.get_gas_balance()}")
                messagebox.showinfo("Wake up NEO", "Morpheus wallet connected successfully")
            except FileNotFoundError:
                messagebox.showerror("Error", "Morpheus wallet file not found.")

    def create_morpheus_wallet(self):
        # Ask user to specify the directory to save the Morpheus wallet
        directory = filedialog.askdirectory(title="Select Directory for Morpheus Wallet")
        if directory:
            self.morpheus_wallet.create_new_wallet(directory=directory)
            self.wallet_address_label.config(text=f"Morpheus Wallet Address: {self.morpheus_wallet.account.address}")
            self.gas_balance_label.config(text=f"Gas Balance: {self.morpheus_wallet.get_gas_balance()}")
            messagebox.showinfo("Wake up NEO", "Morpheus wallet created successfully")

    def set_wallet_directory(self):
        directory = filedialog.askdirectory(initialdir=self.wallets_directory, title="Select Directory for Wallets")
        if directory:
            self.wallets_directory = directory
            messagebox.showinfo("Success", f"Wallets will be saved to: {self.wallets_directory}")


# ------------------------------
# Main Program Entry Point
# ------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = KeyMakerApp(root)
    root.mainloop()
