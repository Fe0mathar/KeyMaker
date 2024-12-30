import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pyzipper

# Local modules
from keymaker_dir.console import ConsoleWindow
from keymaker_dir.stats import StatsManager
from keymaker_dir.exporter import WalletExporter
from keymaker_dir.neo_cli import NeoCliManager
from keymaker_dir.wallet_manager import WalletManager

class KeyMakerApp:
    """
    Main GUI for KeyMaker, integrating:
      - ConsoleWindow for local wallet creation and Flow 1/2
      - Morpheus connectivity (via wallet_manager)
      - Stats & charts (StatsManager)
      - Address exporting (WalletExporter)
    
    The user flows remain the same: 
      - Flow 1: Morpheus not connected => local commands only
      - Flow 2: Morpheus connected => GPT, Trinity, advanced logic
    
    FaceFusion / LadyInRed:
      - If "ladyinred" (or "facefusion") is triggered from the console, 
        we can open a browser or start a local server for FaceFusion 
        (not shown in this UI code).
      - This file remains the standard KeyMaker UI with diagrams on the center 
        and console on the right, no toggling for FaceFusion here.
    """

    def __init__(self, master, vault_instance, wallet_manager, neo_cli_manager):
        """
        :param master:        Root Tk window
        :param vault_instance: A Vault object (with .path & .password), from VaultWindow
        :param wallet_manager: Used strictly for Morpheus connectivity
        :param neo_cli_manager: Manages Neo-CLI
        """
        self.master = master
        self.vault = vault_instance
        self.wallet_manager = wallet_manager
        self.neo_cli_manager = neo_cli_manager

        # Additional managers
        self.exporter = WalletExporter(self.vault.path, self.vault.password)
        self.stats_manager = StatsManager(self.vault.path, self.vault.password)

        # Track Morpheus / wallet details
        self.morpheus_address = tk.StringVar(value="N/A")
        self.morpheus_gas = tk.StringVar(value="N/A")
        self.morpheus_tx_estimates = tk.StringVar(value="N/A")
        self.morpheus_contract_estimates = tk.StringVar(value="N/A")

        self.morpheus_connected = False
        self.morpheus_wallet_zip_path = None
        self.morpheus_wallet_password = None

        # Basic window config
        self.master.title("KeyMaker")
        self.master.geometry("1600x900")
        self.master.configure(bg="black")
        self.master.resizable(True, True)

        # Grid layout
        self.master.grid_columnconfigure(0, minsize=400, weight=0)  # left panel
        self.master.grid_columnconfigure(1, weight=1)               # center panel
        self.master.grid_columnconfigure(2, minsize=600, weight=0)  # right panel
        self.master.grid_rowconfigure(0, weight=1)

        self.update_id = None  # If we need periodic tasks
        self.setup_ui()

        # Graceful close
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """Configure the main layout: left, center, right frames + hidden API key frame."""
        self.setup_left_frame()
        self.setup_center_frame()
        self.setup_right_frame()
        self.setup_api_key_frame()

    # -------------------------------------------------------------------------
    # Left Panel
    # -------------------------------------------------------------------------
    def setup_left_frame(self):
        """Left panel with action buttons + Morpheus wallet info."""
        self.left_frame = tk.Frame(self.master, bg="#15191F")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(15, 5), pady=(15, 15))

        self.actions = [
            "Create Wallets",
            "Export Addresses",
            "Connect Morpheus Wallet",
            "Check CLI Status",
            "Update Charts",
            "Exit",
        ]
        for action in self.actions:
            tk.Button(
                self.left_frame,
                text=action,
                command=lambda a=action: self.handle_action(a),
                font=("Courier", 12),
                bg="black",
                fg="#20E8AA",
                relief="ridge",
                width=32,
                height=2
            ).pack(pady=15, padx=15)

        tk.Label(
            self.left_frame,
            text="Morpheus Wallet Info",
            bg="#15191F",
            fg="#20E8AA",
            font=("Courier", 14, "bold")
        ).pack(pady=(20, 10), anchor="s")

        # Morpheus fields
        fields = [
            ("Public Address:", self.morpheus_address),
            ("GAS Balance:", self.morpheus_gas),
            ("Estimated Transactions:", self.morpheus_tx_estimates),
            ("Estimated Contracts:", self.morpheus_contract_estimates),
        ]
        for label, var in fields:
            tk.Label(
                self.left_frame,
                text=label,
                bg="#15191F",
                fg="#20E8AA",
                font=("Courier", 12)
            ).pack(anchor="w", padx=10)
            tk.Label(
                self.left_frame,
                textvariable=var,
                bg="#15191F",
                fg="#20E8AA",
                font=("Courier", 12, "bold"),
                width=40
            ).pack(anchor="w", padx=10, pady=2)

        # Key symbol for API keys, shown after Morpheus connect
        self.key_symbol_button = None

    # -------------------------------------------------------------------------
    # Center Panel
    # -------------------------------------------------------------------------
    def setup_center_frame(self):
        """Center panel for charts or stats-based data."""
        self.center_frame = tk.Frame(self.master, bg="#15191F")
        self.center_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=(15, 15))
        self.diagram_frames = self.center_frame
        self.update_diagrams()

    # -------------------------------------------------------------------------
    # Right Panel
    # -------------------------------------------------------------------------
    def setup_right_frame(self):
        """Right panel with CRT image + console."""
        self.right_frame = tk.Frame(self.master, bg="black")
        self.right_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 15), pady=(15, 15))

        # Attempt to load CRT image
        try:
            crt_image = Image.open("F:/KeyMaker/crt.png").resize((600, 450))
            crt_photo = ImageTk.PhotoImage(crt_image)
            crt_label = tk.Label(self.right_frame, image=crt_photo, bg="black")
            crt_label.pack(pady=5)
            self.right_frame.crt_photo = crt_photo  # keep reference to avoid GC
        except Exception as e:
            print(f"[GUI] Error loading CRT image: {e}")

        # ConsoleWindow
        self.console_window = ConsoleWindow(
            self.right_frame,
            self.vault,
            self.exporter,
            self.neo_cli_manager,
            scale=1.2
        )
        # No second "WAKE UP, NEO..." here (the console constructor does it once).

        # Place console items
        self.console_window.text_widget.place(x=80, y=100, width=460, height=280)
        self.console_window.prompt_entry.place(x=60, y=420, width=500)

        # Let wallet_manager use the same console for logging Morpheus operations
        self.wallet_manager.console_window = self.console_window

        # Callback so console can update Morpheus gas in the left panel
        self.console_window.on_gas_update = self.set_morpheus_gas

    # -------------------------------------------------------------------------
    # API Key Frame (Hidden)
    # -------------------------------------------------------------------------
    def setup_api_key_frame(self):
        """Hidden frame for user-provided API keys (ChatGPT, Twitter, etc.)."""
        self.api_key_frame = tk.Frame(self.master, bg="#15191F")

        tk.Label(
            self.api_key_frame,
            text="Enter Your API Keys",
            bg="#15191F",
            fg="#20E8AA",
            font=("Courier", 14, "bold")
        ).pack(pady=(20, 10))

        self.api_keys_entries = {}
        labels = [
            "ChatGPT API Key",
            "Twitter Consumer Key",
            "Twitter Consumer Secret",
            "Twitter Access Token",
            "Twitter Access Token Secret",
        ]
        for lbl_text in labels:
            lbl = tk.Label(
                self.api_key_frame,
                text=lbl_text,
                bg="#15191F",
                fg="#20E8AA",
                font=("Courier", 12)
            )
            lbl.pack(anchor="w", padx=10)
            ent = tk.Entry(
                self.api_key_frame,
                bg="black",
                fg="#20E8AA",
                font=("Courier", 12),
                width=40
            )
            ent.pack(anchor="w", padx=10, pady=2)
            self.api_keys_entries[lbl_text] = ent

        btn_frame = tk.Frame(self.api_key_frame, bg="#15191F")
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame,
            text="SAVE",
            command=self.save_api_keys,
            bg="black",
            fg="#00FF00",
            font=("Courier", 12, "bold"),
            relief="ridge",
            width=12,
            height=2
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            btn_frame,
            text="CANCEL",
            command=self.hide_api_key_frame,
            bg="black",
            fg="#FF4444",
            font=("Courier", 12, "bold"),
            relief="ridge",
            width=12,
            height=2
        ).pack(side=tk.LEFT, padx=10)

    def show_key_symbol(self):
        """Once Morpheus is connected, show the 🔑 button in bottom of left panel."""
        if not self.key_symbol_button:
            self.key_symbol_button = tk.Button(
                self.left_frame,
                text="🔑",
                command=self.show_api_key_frame,
                font=("Courier", 12, "bold"),
                bg="black",
                fg="#20E8AA",
                relief="ridge",
                width=4,
                height=1
            )
            self.key_symbol_button.pack(side=tk.BOTTOM, pady=(10, 10))

    def show_api_key_frame(self):
        """Hide the left frame, show the api_key_frame, load existing keys from Morpheus zip if possible."""
        self.left_frame.grid_forget()
        self.api_key_frame.grid(row=0, column=0, sticky="nsew", padx=(15, 10), pady=(15, 15))

        if self.morpheus_connected and self.morpheus_wallet_zip_path and self.morpheus_wallet_password:
            try:
                with pyzipper.AESZipFile(self.morpheus_wallet_zip_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(self.morpheus_wallet_password)
                    if "api_keys.txt" in zf.namelist():
                        data = zf.read("api_keys.txt").decode("utf-8")
                        for line in data.splitlines():
                            if ":" in line:
                                key_name, val = line.split(":", 1)
                                k = key_name.strip()
                                v = val.strip()
                                if k in self.api_keys_entries:
                                    self.api_keys_entries[k].delete(0, tk.END)
                                    self.api_keys_entries[k].insert(0, v)
            except Exception as e:
                print(f"[GUI] Could not load existing api_keys.txt: {e}")

    def hide_api_key_frame(self):
        """Hide the api_key_frame, restore the left_frame layout."""
        self.api_key_frame.grid_forget()
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(15, 5), pady=(15, 15))

    def save_api_keys(self):
        """
        Save user-provided keys into 'api_keys.txt' inside Morpheus wallet zip,
        properly overwriting the old file.
        """
        if not (self.morpheus_connected and self.morpheus_wallet_zip_path and self.morpheus_wallet_password):
            messagebox.showerror("Error", "Morpheus wallet not connected or missing zip path/password.")
            return

        lines = []
        for lbl_text, entry in self.api_keys_entries.items():
            val = entry.get().strip()
            lines.append(f"{lbl_text}: {val}")

        combined = "\n".join(lines)

        try:
            # read old files except api_keys.txt
            old_files = {}
            with pyzipper.AESZipFile(self.morpheus_wallet_zip_path, 'r', encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.morpheus_wallet_password)
                for name in zf.namelist():
                    if name != "api_keys.txt":
                        old_files[name] = zf.read(name)

            # rewrite zip in 'w' mode
            with pyzipper.AESZipFile(
                self.morpheus_wallet_zip_path,
                'w',
                compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES
            ) as zf:
                zf.setpassword(self.morpheus_wallet_password)
                for name, data in old_files.items():
                    zf.writestr(name, data)
                zf.writestr("api_keys.txt", combined)

            messagebox.showinfo("Success", "API keys saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save API keys: {e}")

        self.hide_api_key_frame()

    # -------------------------------------------------------------------------
    # Button Actions
    # -------------------------------------------------------------------------
    def handle_action(self, action):
        """Dispatch from left-frame button clicks."""
        if action == "Create Wallets":
            self.console_window.log("OPERATOR: Wallet creation in progress...", tag="operator", color="#00FF00")
            self.console_window.request_wallet_creation()

        elif action == "Export Addresses":
            self.console_window.log("OPERATOR: Exporting Addresses initiated...", tag="operator", color="#00FF00")
            self.console_window.export_addresses()

        elif action == "Connect Morpheus Wallet":
            self.connect_morpheus_wallet()

        elif action == "Check CLI Status":
            self.check_cli_status()

        elif action == "Update Charts":
            self.console_window.log("OPERATOR: Updating diagrams...", tag="operator", color="#00FF00")
            self.update_diagrams()

        elif action == "Exit":
            self.master.quit()

    def connect_morpheus_wallet(self):
        """Ask user for Morpheus ZIP, then password, then call wallet_manager.connect_morpheus_wallet."""
        zip_path = filedialog.askopenfilename(
            title="Select Morpheus Wallet Vault",
            filetypes=[("ZIP files", "*.zip")]
        )
        if not zip_path:
            self.console_window.log(
                "OPERATOR: No file selected for Morpheus Wallet connection.",
                tag="operator", color="#00FF00"
            )
            return

        # Ensure we aren't stuck in leftover password flow
        self.console_window.cli_password_in_progress = False

        pass_prompt = tk.Toplevel(self.master)
        pass_prompt.title("Enter Morpheus Vault Password")
        pass_prompt.configure(bg="black")
        pass_prompt.geometry("500x180+500+300")

        tk.Label(
            pass_prompt,
            text="Please enter the vault password for your Morpheus .zip:",
            bg="black",
            fg="#20E8AA",
            font=("Courier", 12),
            wraplength=480
        ).pack(pady=(10, 10), padx=10)

        password_var = tk.StringVar()
        pass_entry = tk.Entry(
            pass_prompt,
            textvariable=password_var,
            show="*",
            bg="black",
            fg="#FFFFFF",
            font=("Courier", 12),
            width=40
        )
        pass_entry.pack(pady=(0, 10))
        pass_entry.focus_set()

        def on_submit():
            pwd = password_var.get().strip()
            pass_prompt.destroy()
            if not pwd:
                self.console_window.log(
                    "OPERATOR: No password entered for Morpheus Wallet.",
                    tag="operator", color="#00FF00"
                )
                return
            self._connect_morpheus_vault(zip_path, pwd)

        tk.Button(
            pass_prompt,
            text="SUBMIT",
            command=on_submit,
            bg="black",
            fg="#00FF00",
            font=("Courier", 12, "bold"),
            relief="ridge",
            width=10,
            height=1
        ).pack(pady=(0, 10))

        pass_prompt.grab_set()
        pass_prompt.wait_window()

    def _connect_morpheus_vault(self, zip_path, password):
        """Call wallet_manager.connect_morpheus_wallet, handle success/fail, show key if success."""
        try:
            def update_gui(wallet_data):
                self.morpheus_address.set(wallet_data.get("public_address", "N/A"))
                self.morpheus_gas.set(wallet_data.get("gas_balance", "N/A"))
                self.morpheus_tx_estimates.set(wallet_data.get("estimated_transactions", "N/A"))
                self.morpheus_contract_estimates.set(wallet_data.get("estimated_contracts", "N/A"))

            wallet_data = self.wallet_manager.connect_morpheus_wallet(
                zip_path,
                password,
                update_gui_callback=update_gui
            )
            self.morpheus_connected = True
            self.morpheus_wallet_zip_path = zip_path
            self.morpheus_wallet_password = (
                password.encode() if isinstance(password, str) else password
            )

            # Also let the console know => so on final pass acceptance => console can recheck API keys
            self.console_window.morpheus_wallet_zip_path = self.morpheus_wallet_zip_path
            self.console_window.morpheus_wallet_password = self.morpheus_wallet_password

            self.show_key_symbol()
        except Exception as e:
            self.console_window.log(
                f"Error connecting Morpheus Wallet: {e}",
                tag="operator",
                color="#FF0000"
            )

    def check_cli_status(self):
        """Check if Neo-CLI is running, log result in console."""
        try:
            if not self.neo_cli_manager.is_running():
                self.console_window.log(
                    "OPERATOR: Neo-CLI Not initiated - connect Morpheus.",
                    tag="operator", color="#FF0000"
                )
            else:
                self.console_window.log(
                    "OPERATOR: Neo-CLI Running: True",
                    tag="operator",
                    color="#00FF00"
                )
        except Exception as e:
            self.console_window.log(
                f"OPERATOR: Error checking Neo-CLI status: {e}",
                tag="operator",
                color="#FF0000"
            )

    def update_diagrams(self):
        """Refresh bar charts in the center using stats_manager data."""
        for widget in self.diagram_frames.winfo_children():
            widget.destroy()

        figure = Figure(figsize=(6.3, 7.2), dpi=100, facecolor="#15191F")
        ax = figure.add_subplot(111)

        dates, full_counts, empty_counts = self.stats_manager.get_wallet_volume_trend()

        bars_full = ax.bar(dates, full_counts, color="#5A9", edgecolor="#00FFAA", width=0.6, label="Full")
        bars_empty = ax.bar(
            dates,
            empty_counts,
            color="#333",
            edgecolor="#00FFAA",
            width=0.6,
            label="Empty",
            bottom=full_counts
        )

        for bar, count in zip(bars_full, full_counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{count}",
                ha="center",
                color="#20E8AA",
                fontsize=10
            )
        for bar, count in zip(bars_empty, empty_counts):
            stacked_bottom = bar.get_y() + bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                stacked_bottom + 0.5,
                f"{count}",
                ha="center",
                color="#FF4444",
                fontsize=10
            )

        ax.set_title("Wallet Volume Trend", color="#20E8AA")
        ax.set_facecolor("#15191F")
        ax.tick_params(colors="#20E8AA")
        ax.spines["bottom"].set_color("#20E8AA")
        ax.spines["left"].set_color("#20E8AA")
        ax.set_xlabel("Creation Date", color="#20E8AA")
        ax.set_ylabel("Volume", color="#20E8AA")
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, fontsize=8, ha="right")
        ax.legend()

        self.volume_figure = FigureCanvasTkAgg(figure, self.diagram_frames)
        self.volume_figure.get_tk_widget().pack(expand=True, fill="both", padx=10, pady=(20, 10))

    def on_closing(self):
        """Cleanup tasks before closing the window."""
        try:
            if self.update_id:
                self.master.after_cancel(self.update_id)
        except AttributeError:
            pass
        self.neo_cli_manager.stop()
        self.master.destroy()

    def set_morpheus_gas(self, gas_balance):
        """Called by console after pass success => updates left panel GAS label."""
        self.morpheus_gas.set(gas_balance)
