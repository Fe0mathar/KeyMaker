import os
import tkinter as tk
from tkinter import filedialog
from threading import Thread
from queue import Queue
from datetime import datetime
from difflib import get_close_matches
import subprocess
import sys
import re

# Matrix aggregator
from keymaker_dir.matrix import Matrix
# AI engine (Seraph) - for Flow 2
from keymaker_dir.ai import AIEngine
# Wallet creation logic
from keymaker_dir.wallet import Wallet


class ConsoleWindow:
    def __init__(self, master, vault, exporter, cli_manager, scale=1.0):
        """
        The main console interface for KeyMaker.

        - Flow 1 (no GPT, Morpheus not connected):
            local commands + CLI commands, or show "Seraph offline..." if unrecognized.
        - Flow 2 (GPT enabled, Morpheus connected):
            all user input is routed to SERAPH for advanced logic/fallback.

        Additionally:
         - We handle a CLI password flow ("OPERATOR: Provide Password.") => 
           the next user input is always a password (not a recognized command).
         - We can link to Trinity for Twitter interactions if needed (via set_trinity).
         - We have:
             "installLIR" => triggers installLIR.py
             "LIR"        => triggers ladyinred.py (opening the UI)
         - We capture lines from LadyInRed output to parse progress for:
             - Downloading / Analysing / Extracting / Processing
           and display them in single-line updates (progress bar).
        """
        self.master = master
        self.vault = vault
        self.exporter = exporter
        self.cli_manager = cli_manager
        self.scale = scale

        # Callback for updating Morpheus GAS in the GUI
        self.on_gas_update = None

        # Trinity instance (for tweets, DMs, etc.), optionally set via set_trinity(...)
        self.trinity = None

        # Multi-wallet creation states
        self.wallet_creation_in_progress = False
        self.wallet_passphrase_in_progress = False
        self.pending_wallet_count = 0
        self.current_passphrase = None

        # Are we awaiting a CLI password from the user?
        self.cli_password_in_progress = False

        # Flag indicating if Morpheus is fully connected => GPT usage allowed
        self.morpheus_unlocked = False

        # --------------------- CONSOLE TEXT WIDGET -----------------------
        self.text_widget = tk.Text(
            master,
            bg="black",
            fg="#00FF00",
            font=("Courier", 12),
            wrap="word",
            width=int(80 * scale),
            height=int(15 * scale),
            bd=1,
            relief="solid"
        )
        self.text_widget.place(x=10, y=10)
        self.text_widget.config(state="disabled")

        # --------------------- PROMPT ENTRY ------------------------------
        self.prompt_var = tk.StringVar()
        self.prompt_entry = tk.Entry(
            master,
            textvariable=self.prompt_var,
            bg="black",
            fg="#FFFFFF",
            font=("Courier", int(14 * scale)),
            width=int(80 * scale),
        )
        self.prompt_entry.place(x=10, y=400)
        self.prompt_entry.bind("<Return>", self.handle_prompt)

        # --------------------- MATRIX CANVAS -----------------------------
        self.canvas = tk.Canvas(
            master,
            bg="black",
            width=int(500 * scale),
            height=int(300 * scale),
            highlightthickness=0
        )
        self.canvas.place(x=15, y=480)

        self.matrix = Matrix(self.canvas, 500, 300, font_path="F:/KeyMaker/MS_Mincho.ttf")
        self.start_matrix_animation()

        # --------------------- AI ENGINE (Seraph) ------------------------
        self.seraph = AIEngine(console=self)

        # --------------------- LOCAL WALLET ------------------------------
        self.local_wallet = Wallet(self.vault.path, self.vault.password)

        # Show initial console line - only once
        self.log("WAKE UP, NEO...")

        # For capturing the external process (ladyinred) if running
        self.lir_process = None

        # Track states for LadyInRed progress logic
        self.lir_current_prefix = None
        self.lir_progress_map = {}        # e.g. {"Downloading": 0..100, "Analysing": ..., ...}
        self.lir_spinners = ['/', '-', '\\', '|']
        self.lir_spinner_states = {}      # e.g. {"Downloading": 0..3, ...}

    def set_trinity(self, trinity_instance):
        """
        Called by main or higher-level code to give the console
        a reference to the Trinity module for Twitter interactions.
        """
        self.trinity = trinity_instance

    # ---------------------------------------------------------------------
    # MATRIX ANIMATION
    # ---------------------------------------------------------------------
    def start_matrix_animation(self):
        try:
            t = Thread(target=self.matrix.start, daemon=True)
            t.start()
            print("[Console] Matrix animation started.")
        except Exception as e:
            print(f"[Console] Error starting Matrix: {e}")

    # ---------------------------------------------------------------------
    # LOGGING
    # ---------------------------------------------------------------------
    def log(self, message, tag=None, color=None):
        """
        Add a line to the console text.
        Check for "TRIGGER: finalize_morpheus_success" => finalize Morpheus connection.
        Also detect "OPERATOR: Provide Password." => set cli_password_in_progress = True
        """
        if message.strip() == "TRIGGER: finalize_morpheus_success":
            self._finalize_morpheus_connection()
            return

        self.text_widget.config(state="normal")
        if tag and color:
            self.text_widget.tag_configure(tag, foreground=color)
            self.text_widget.insert("end", message + "\n", tag)
        else:
            self.text_widget.insert("end", message + "\n")
        self.text_widget.see("end")
        self.text_widget.config(state="disabled")

        # aggregator-based matrix
        self.matrix.queue_message(message)

        check_line = message.lower().strip()
        if ("operator:" in check_line) and ("provide password." in check_line):
            self.cli_password_in_progress = True

        if ("neo> password:" in check_line or "you have to open the wallet first" in check_line):
            if not self.cli_password_in_progress:
                self.log("OPERATOR: Detected leftover partial open wallet state. Forcing CLI stop.",
                         tag="operator", color="#FF0000")
                self.force_cli_stop("CLI leftover. Re-click 'Connect Morpheus Wallet' to start fresh.")

    def _finalize_morpheus_connection(self):
        """
        Clears console, sets morpheus_unlocked = True => GPT usage allowed.
        Possibly re-check api_keys.txt if the .zip path is known.
        """
        self.clear()
        self.morpheus_unlocked = True
        self.log("OPERATOR: Morpheus Wallet Connected.", tag="operator", color="#00FF00")

        if hasattr(self, "morpheus_wallet_zip_path") and hasattr(self, "morpheus_wallet_password"):
            self.seraph.morpheus_wallet_zip_path = self.morpheus_wallet_zip_path
            self.seraph.morpheus_wallet_zip_password = self.morpheus_wallet_password
            self.seraph.recheck_api_keys()

    def clear(self):
        """Clears the console text widget."""
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.config(state="disabled")

    # ---------------------------------------------------------------------
    # Handling User Prompt
    # ---------------------------------------------------------------------
    def handle_prompt(self, event):
        """
        If cli_password_in_progress == True => next user input is password,
        skip recognized commands / GPT logic, pass directly to CLI password method.
        Otherwise => proceed with normal flows (Flow 1 or Flow 2).
        """
        user_input = self.prompt_var.get().strip()
        if not user_input:
            return
        self.prompt_var.set("")
        self.log(f"USER: {user_input}", tag="user", color="#FFFFFF")

        # If the console is waiting for a CLI password => treat user_input as the password
        if self.cli_password_in_progress:
            self.execute_cli_password(user_input)
            return

        # If in multi-wallet creation flow
        if self.wallet_creation_in_progress:
            self._handle_wallet_creation_flow(user_input)
            return

        # Flow decision:
        if not self.morpheus_unlocked:
            # Flow 1 => No GPT
            self.handle_flow1_input(user_input)
        else:
            # Flow 2 => pass to SERAPH
            self.seraph.respond_to_query(user_input)

    # ---------------------------------------------------------------------
    # Flow 1 logic (No GPT)
    # ---------------------------------------------------------------------
    def handle_flow1_input(self, user_input):
        """
        - local commands
        - CLI commands
        - or "Seraph offline..."

        Also includes:
            "installLIR" => runs installLIR.py
            "LIR"        => runs ladyinred.py
        """
        recognized_local = self.is_local_command(user_input)
        if recognized_local:
            self.log(f"OPERATOR: Executing local command => {recognized_local.__name__}",
                     tag="operator", color="#00FF00")
            recognized_local()
            return

        if self.is_cli_command(user_input):
            self.execute_cli_command(user_input)
            return

        self.log("OPERATOR: Seraph is offline until Morpheus wallet is connected // Command not recognized",
                 tag="operator", color="#00FF00")

    def is_local_command(self, user_input):
        """
        Local commands for Flow 1:
          - 'create wallets'
          - 'export addresses'
          - 'update charts'
          - 'installLIR' => self.launch_installLIR
          - 'LIR'        => self.launch_ladyinred
        """
        known_locals = {
            "create wallets": self.request_wallet_creation,
            "export addresses": self.export_addresses,
            "update charts": self.handle_update_charts,
            "installlir": self.launch_installLIR,
            "lir": self.launch_ladyinred
        }
        synonyms = {
            "create wallets": ["create wallet", "make wallets"],
            "export addresses": ["export address", "export wallet addresses"],
            "update charts": ["refresh charts", "update chart"],
            "installlir": ["install lir", "install ladyinred", "install facefusion"],
            "lir": ["ladyinred", "facefusion", "faceswap", "fusion time"]
        }

        lc_input = user_input.lower()
        if lc_input in known_locals:
            return known_locals[lc_input]

        for cmd, syns in synonyms.items():
            if lc_input in syns:
                return known_locals[cmd]
        return None

    def launch_installLIR(self):
        """
        Runs the installLIR.py script to install LadyInRed dependencies.
        """
        self.log("OPERATOR: Installing LadyInRed (FaceFusion). Please wait...", tag="operator", color="#00FF00")
        try:
            script_path = os.path.join("keymaker_dir", "installLIR.py")
            subprocess.check_call([sys.executable, script_path, "--onnxruntime=default"])
            self.log("OPERATOR: LadyInRed (FaceFusion) installed successfully!", tag="operator", color="#00FF00")
        except subprocess.CalledProcessError as e:
            self.log(f"OPERATOR: Installation failed: {e}", tag="operator", color="#FF0000")

    def launch_ladyinred(self):
        """
        Runs ladyinred.py to open the UI, capturing stdout in real time
        to parse progress lines for (Downloading / Analysing / Extracting / Processing).
        We keep a single or two-line block in the console for each prefix's progress.
        """
        self.log("OPERATOR: Launching LadyInRed UI...", tag="operator", color="#00FF00")

        try:
            script_path = os.path.join("keymaker_dir", "ladyinred.py")
            # We'll capture stdout so we can parse lines
            self.lir_process = subprocess.Popen(
                [sys.executable, script_path, "run", "--open-browser"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True  # so we get string lines
            )
            # Start a thread to read lines from the process
            t = Thread(target=self._capture_lir_output, args=(self.lir_process,), daemon=True)
            t.start()

            self.log("OPERATOR: LadyInRed triggered. (Browser UI should open)", 
                     tag="operator", color="#00FF00")

        except Exception as e:
            self.log(f"OPERATOR: Error launching LadyInRed: {e}", tag="operator", color="#FF0000")

    def _capture_lir_output(self, process):
        """
        Reads lines from ladyinred process stdout in real time,
        looks for progress patterns, logs them in console with single-line progress.
        """
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                # The process ended
                break
            if line:
                line = line.rstrip("\n\r")
                parsed = self._parse_lir_line(line)
                if parsed is not None:
                    # If we have a recognized prefix & percentage => update progress
                    self._update_lir_progress(parsed)
                else:
                    # Optionally show raw lines or skip
                    # self.log(f"LADY IN RED (raw): {line}", tag="ladyinred", color="#FF55FF")
                    pass

        # process ended
        self.log("LADY IN RED: process finished.", tag="ladyinred", color="#FF55FF")

    def _parse_lir_line(self, line):
        """
        Checks if the line matches a progress pattern:
          - "Downloading:", "Analysing:", "Extracting:", "Processing:"
          - looks for integer percent
          - optionally a speed (e.g. "1.06frame/s" or "12.6B/s").

        Returns a dict:
          {"prefix": <str>, "value": <int>, "speed": <str or None>}
        or None if not recognized.
        """
        # Quick search for prefix
        # e.g. "Downloading: 100%|", "Analysing:", "Extracting:", "Processing:"
        prefix_match = re.search(r"^(Downloading|Analysing|Extracting|Processing):\s*", line)
        if not prefix_match:
            return None
        prefix = prefix_match.group(1)  # e.g. "Processing"

        # Now search for a percentage, e.g. " 12%" or "100%"
        percent_match = re.search(r"(\d+)%", line)
        if not percent_match:
            # maybe 0 or no percent found => handle partial
            # you can default to 0 or skip
            return None
        p_str = percent_match.group(1)
        try:
            val = int(p_str)
        except:
            return None

        # Speed => either something like "([\d\.]+B/s)" or "([\d\.]+frame/s)"
        speed_str = None
        speed_b = re.search(r"([\d\.]+B/s)", line)
        if speed_b:
            speed_str = speed_b.group(1)
        else:
            speed_f = re.search(r"([\d\.]+frame/s)", line)
            if speed_f:
                speed_str = speed_f.group(1)

        return {
            "prefix": prefix,   # "Downloading", "Analysing", etc.
            "value": val,       # 0..100
            "speed": speed_str  # "12.6B/s" or "1.06frame/s" or None
        }

    def _update_lir_progress(self, parsed):
        """
        We keep one console block (two lines) per prefix.
        Overwrite those two lines with the updated progress & spinner each time.
        """
        prefix = parsed["prefix"]  # e.g. "Processing"
        val = parsed["value"]      # integer from 0..100
        speed = parsed["speed"]    # e.g. "1.06frame/s" or None

        # If prefix changed, finalize the old prefix
        if prefix != self.lir_current_prefix:
            if self.lir_current_prefix is not None:
                # e.g. "LADY IN RED: Finished Analysing"
                self.log(f"LADY IN RED: Finished {self.lir_current_prefix}",
                         tag="ladyinred", color="#FF55FF")

            self.lir_current_prefix = prefix
            self.lir_progress_map[prefix] = 0
            self.lir_spinner_states[prefix] = 0
            self.log(f"LADY IN RED: Starting {prefix} ...", tag="ladyinred", color="#FF55FF")

        # clamp val to 0..100
        p = max(0, min(val, 100))
        self.lir_progress_map[prefix] = p

        # Update spinner index for this prefix
        idx = self.lir_spinner_states[prefix]
        spinner_char = self.lir_spinners[idx]
        idx = (idx + 1) % len(self.lir_spinners)
        self.lir_spinner_states[prefix] = idx

        # Build first line: e.g. "LADY IN RED: Processing => 25% (speed=...)" 
        text_line = f"LADY IN RED: {prefix} => {p}%"
        if speed:
            text_line += f" (speed={speed})"

        # Build the progress bar line
        bar_len = 10
        progress_bar = [' '] * bar_len
        slot_index = int(p / 10)  # each 10% is 1 chunk
        for i in range(bar_len):
            if i < slot_index:
                progress_bar[i] = '#'
            elif i == slot_index:
                progress_bar[i] = spinner_char
            else:
                progress_bar[i] = ' '

        bar_display = f"Progress: [{''.join(progress_bar)}] {p}%"

        # Overwrite the previous TWO lines in the console
        self.text_widget.config(state="normal")
        try:
            # remove last two lines
            self.text_widget.delete("end-3l", "end-1l")
        except:
            pass

        # Insert new lines
        self.text_widget.insert("end", text_line + "\n", "ladyinred")
        self.text_widget.insert("end", bar_display + "\n", "ladyinred")
        self.text_widget.config(state="disabled")

    def launch_facefusion(self):
        """
        Legacy stub if you wanted a 'facefusion' command separate from 'LIR'.
        Currently not used but can unify or remove as needed.
        """
        self.log("OPERATOR: FaceFusion triggered. (Open your browser or external interface)",
                 tag="operator", color="#00FF00")

    def is_cli_command(self, user_input):
        """
        Minimal check if user_input is a recognized CLI command in Flow 1.
        """
        known_cli_starts = [
            "open wallet",
            "close wallet",
            "list asset",
            "list address",
            "show state",
            "exit",
            "help",
            "send",
            "create wallet"
        ]
        lc_input = user_input.lower()
        for c in known_cli_starts:
            if lc_input.startswith(c):
                return True
        return False

    # ---------------------------------------------------------------------
    # CLI Password Flow
    # ---------------------------------------------------------------------
    def execute_cli_password(self, password):
        """
        If user typed a password after "OPERATOR: Provide Password." 
        => pass to CLI, see if correct => finalize or forcibly stop leftover.
        Then set cli_password_in_progress = False so next input is normal.
        """
        try:
            resp = self.cli_manager.execute_cli_command(password)
            if resp:
                wrong_pass = False
                for line in resp.splitlines():
                    self.log(f"CLI Output: {line}", tag="operator", color="#00FF00")
                    if "wrong password" in line.lower() or "invalid password" in line.lower():
                        wrong_pass = True

                if wrong_pass:
                    self.force_cli_stop("Wrong password. CLI is stopped. Re-click 'Connect Morpheus Wallet'.")
                else:
                    self.log("OPERATOR: Password accepted. Checking 'list asset' for final confirmation...",
                             tag="operator", color="#00FF00")
                    self.run_list_asset_and_finalize()
        except Exception as e:
            self.log(f"OPERATOR: CLI Error: {e}", tag="operator", color="#FF0000")
            self.force_cli_stop("CLI encountered an error. Re-click 'Connect Morpheus Wallet'.")
        finally:
            self.cli_password_in_progress = False

    def run_list_asset_and_finalize(self):
        """
        "list asset" => parse 'GAS:' => if found => finalize Morpheus => 'TRIGGER: finalize_morpheus_success'
        """
        try:
            resp = self.cli_manager.execute_cli_command("list asset")
            if not resp:
                self.log("OPERATOR: 'list asset' gave no response or timed out. Stopping CLI.",
                         tag="operator", color="#FF0000")
                self.force_cli_stop("No valid 'list asset' response. Re-click 'Connect Morpheus Wallet'.")
                return

            self.log("[Console] 'list asset' full response:", tag="operator", color="#00FF00")
            for line in resp.splitlines():
                self.log(f"CLI Output: {line}", tag="operator", color="#00FF00")

            # Attempt parse GAS
            gas_balance = "N/A"
            for line in resp.splitlines():
                if "gas:" in line.lower():
                    parts = line.lower().split("gas:")
                    if len(parts) > 1:
                        potential = parts[1].strip().split()[0]
                        try:
                            float(potential)
                            gas_balance = potential
                        except:
                            pass
                    break

            if gas_balance != "N/A":
                if self.on_gas_update:
                    self.on_gas_update(gas_balance)
                self.log("TRIGGER: finalize_morpheus_success")
            else:
                self.log("OPERATOR: Could not parse a valid GAS from 'list asset'. Stopping CLI.",
                         tag="operator", color="#FF0000")
                self.force_cli_stop("No valid GAS. Re-click 'Connect Morpheus Wallet'.")

        except Exception as e:
            self.log(f"OPERATOR: CLI Error in 'list asset': {e}", tag="operator", color="#FF0000")
            self.force_cli_stop("CLI error. Re-click 'Connect Morpheus Wallet'.")

    def force_cli_stop(self, reason_message):
        """
        Stops the CLI so no leftover open wallet remains, sets morpheus_unlocked = False.
        """
        self.log(f"OPERATOR: {reason_message}", tag="operator", color="#FF0000")
        try:
            self.cli_manager.execute_cli_command("close wallet")
            self.cli_manager.execute_cli_command("exit")
        except:
            pass
        self.cli_manager.stop()
        self.cli_password_in_progress = False
        self.morpheus_unlocked = False

    # ---------------------------------------------------------------------
    # Multi-Wallet Creation (Local Vault)
    # ---------------------------------------------------------------------
    def request_wallet_creation(self):
        self.wallet_creation_in_progress = True
        self.wallet_passphrase_in_progress = False
        self.pending_wallet_count = 0
        self.current_passphrase = None
        self.log("OPERATOR: How many wallets would you like to create?",
                 tag="operator", color="#00FF00")

    def _handle_wallet_creation_flow(self, user_input):
        """
        If already waiting for passphrase => set that, create wallets
        Otherwise => interpret user_input as the number of wallets.
        """
        if self.wallet_passphrase_in_progress:
            # We got passphrase
            self.current_passphrase = user_input
            self.wallet_passphrase_in_progress = False
            self.log("OPERATOR: Passphrase received. Proceeding with wallet creation...",
                     tag="operator", color="#00FF00")
            self.create_wallets(self.pending_wallet_count, self.current_passphrase)
        else:
            # Expecting number of wallets
            try:
                count = int(user_input)
                if count > 0:
                    self.wallet_passphrase_in_progress = True
                    self.pending_wallet_count = count
                    self.log("OPERATOR: Please provide a passphrase for wallet encryption.",
                             tag="operator", color="#00FF00")
                else:
                    self.log("OPERATOR: Please specify a number > 0.",
                             tag="operator", color="#00FF00")
            except ValueError:
                self.log("OPERATOR: Invalid input. Please enter a numeric wallet count.",
                         tag="operator", color="#00FF00")

    def create_wallets(self, count, passphrase):
        Thread(target=self._create_wallets_thread, args=(count, passphrase), daemon=True).start()

    def _create_wallets_thread(self, count, passphrase):
        try:
            progress_bar = [' '] * 10
            spinner = ['/', '-', '\\', '|']
            spinner_index = 0

            def update_progress(percent):
                nonlocal spinner_index
                slot_index = percent // 10
                for i in range(len(progress_bar)):
                    if i < slot_index:
                        progress_bar[i] = '#'
                    elif i == slot_index:
                        progress_bar[i] = spinner[spinner_index % len(spinner)]
                        spinner_index = (spinner_index + 1) % len(spinner)
                    else:
                        progress_bar[i] = ' '

                bar_display = f"Progress: [{''.join(progress_bar)}] {percent}%"
                self.text_widget.config(state="normal")
                try:
                    self.text_widget.delete("end-2l", "end-1l")
                except:
                    pass
                self.text_widget.insert("end", bar_display + "\n", "operator")
                self.text_widget.config(state="disabled")

            total_created = 0
            for i in range(count):
                new_file = self.local_wallet.create_wallet(passphrase)
                total_created += 1

                pct = int((i + 1) / count * 100)
                update_progress(pct)

            self.log(f"OPERATOR: Wallet creation completed. Created {total_created} wallets.",
                     tag="operator", color="#00FF00")

            wallet_files = self.local_wallet.list_wallets()
            self.log(f"OPERATOR: Now {len(wallet_files)} total wallets in local vault.",
                     tag="operator", color="#00FF00")
        except Exception as e:
            self.log(f"OPERATOR: Error creating wallets: {e}", tag="operator", color="#FF0000")
        finally:
            self.reset_wallet_creation_state()

    def reset_wallet_creation_state(self):
        self.wallet_creation_in_progress = False
        self.wallet_passphrase_in_progress = False
        self.pending_wallet_count = 0
        self.current_passphrase = None

    # ---------------------------------------------------------------------
    # Export addresses with progress
    # ---------------------------------------------------------------------
    def export_addresses(self):
        filename = filedialog.asksaveasfilename(
            title="Save Wallet Addresses",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")]
        )
        if filename:
            self.log("OPERATOR: Exporting Addresses initiated...", tag="operator", color="#00FF00")
            self.track_progress(
                task=lambda cb: self.exporter.export_addresses(filename, cb),
                init_message=None,
                completion_message=f"OPERATOR: Addresses exported to {filename}"
            )

    def track_progress(self, task, init_message, completion_message):
        Thread(
            target=self._track_progress_thread,
            args=(task, init_message, completion_message),
            daemon=True
        ).start()

    def _track_progress_thread(self, task, init_message, completion_message):
        try:
            if init_message:
                self.log(init_message, tag="operator", color="#00FF00")

            progress_bar = [' '] * 10
            spinner = ['/', '-', '\\', '|']
            spinner_index = 0

            def update_progress(percent):
                nonlocal spinner_index
                slot_index = percent // 10
                for i in range(len(progress_bar)):
                    if i < slot_index:
                        progress_bar[i] = '#'
                    elif i == slot_index:
                        progress_bar[i] = spinner[spinner_index % len(spinner)]
                        spinner_index = (spinner_index + 1) % len(spinner)
                    else:
                        progress_bar[i] = ' '

                bar_display = f"Progress: [{''.join(progress_bar)}] {percent}%"
                self.text_widget.config(state="normal")
                try:
                    self.text_widget.delete("end-2l", "end-1l")
                except:
                    pass
                self.text_widget.insert("end", bar_display + "\n", "operator")
                self.text_widget.config(state="disabled")

            task(update_progress)
            if completion_message:
                self.log(completion_message, tag="operator", color="#00FF00")

        except Exception as e:
            self.log(f"OPERATOR: Error: {e}", tag="operator", color="#FF0000")

    # ---------------------------------------------------------------------
    # A stub method for "update charts"
    # ---------------------------------------------------------------------
    def handle_update_charts(self):
        """
        A placeholder if user or SERAPH references "update charts".
        In the GUI, you might refresh the stats. Here, we just log a stub.
        """
        self.log("OPERATOR: 'update charts' called. (Stub - no chart logic implemented)",
                 tag="operator", color="#00FF00")

    # ---------------------------------------------------------------------
    # AI -> Console bridging
    # ---------------------------------------------------------------------
    def handle_ai_command(self, command):
        """
        Called by AIEngine for recognized KeyMaker commands
        (e.g. 'request_wallet_creation', 'export_addresses', 'list_asset', 'installLIR', 'LIR', etc.).
        """
        if command == "request_wallet_creation":
            self.request_wallet_creation()
        elif command == "export_addresses":
            self.export_addresses()
        elif command == "list_asset":
            self.log("OPERATOR: Attempting to list assets (CLI)...", tag="operator", color="#00FF00")
            self.execute_cli_command("list asset")
        elif command == "installLIR":
            self.launch_installLIR()
        elif command == "LIR":
            self.launch_ladyinred()
        else:
            self.log("SERAPH: Command recognized but not implemented in console.py",
                     tag="seraph", color="#FFFF55")

    def execute_cli_command(self, command):
        """
        If SERAPH or user recognized a CLI command, run it,
        log lines, forcibly stop leftover if wrong pass or leftover.
        """
        try:
            resp = self.cli_manager.execute_cli_command(command)
            if resp:
                for line in resp.splitlines():
                    self.log(f"CLI Output: {line}", tag="operator", color="#00FF00")

                    # detect wrong password or leftover
                    if "wrong password" in line.lower() or "invalid password" in line.lower():
                        self.force_cli_stop("Wrong password from SERAPH command. Re-click 'Connect Morpheus Wallet'.")
                        return
                    if ("neo> password:" in line.lower() or "you have to open the wallet first" in line.lower()):
                        if not self.cli_password_in_progress:
                            self.force_cli_stop("Leftover open wallet from SERAPH command. Re-click 'Connect Morpheus Wallet'.")
        except Exception as e:
            self.log(f"OPERATOR: CLI Error: {e}", tag="operator", color="#FF0000")
