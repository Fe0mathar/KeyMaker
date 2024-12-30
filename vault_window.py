import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageSequence
from keymaker_dir.vault import Vault


class VaultWindow:
    def __init__(self, master, vault, on_vault_success):
        self.master = master
        self.vault = vault
        self.on_vault_success = on_vault_success
        self.animation_id = None
        self.frames = []
        self.create_vault_window()

    def create_vault_window(self):
        """Setup the Vault Setup window UI."""
        self.master.title("Vault Setup")
        self.master.configure(bg="black")
        self.master.geometry("400x450")  # Adjusted height for a compact interface

        # Set custom icon
        try:
            custom_icon = tk.PhotoImage(file="F:/KeyMaker/neo.png")
            self.master.iconphoto(True, custom_icon)
        except Exception as e:
            print(f"[VaultWindow] Error loading custom icon: {e}")

        # Load animated GIF
        try:
            gif_path = "F:/KeyMaker/matrix.gif"
            gif = Image.open(gif_path)
            self.frames = [ImageTk.PhotoImage(frame.copy()) for frame in ImageSequence.Iterator(gif)]
            self.gif_label = tk.Label(self.master, bg="black")
            self.gif_label.pack(pady=5)
            self.animate_gif()
        except Exception as e:
            print(f"[VaultWindow] Error loading GIF: {e}")

        # Add buttons
        button_font = ("Matrix", 14) if os.path.exists("F:/KeyMaker/matrix.ttf") else ("Arial", 14)
        button_color = "#00FF00"
        button_width = 25
        button_height = 2
        button_padding = 15

        specify_button = tk.Button(
            self.master,
            text="SPECIFY EXISTING VAULT",
            command=self.specify_existing_vault,
            font=button_font,
            bg="black",
            fg=button_color,
            width=button_width,
            height=button_height,
            relief="ridge"
        )
        specify_button.pack(pady=button_padding)

        create_button = tk.Button(
            self.master,
            text="CREATE NEW VAULT",
            command=self.create_new_vault,
            font=button_font,
            bg="black",
            fg=button_color,
            width=button_width,
            height=button_height,
            relief="ridge"
        )
        create_button.pack(pady=button_padding)

    def animate_gif(self, index=0):
        """Animate the GIF in the vault window."""
        if self.frames:
            self.gif_label.config(image=self.frames[index])
            self.animation_id = self.master.after(100, self.animate_gif, (index + 1) % len(self.frames))

    def stop_animation(self):
        """Stop the animation when transitioning to another window."""
        if self.animation_id:
            try:
                self.master.after_cancel(self.animation_id)
            except Exception:
                pass  # Ignore any cancellation errors
            self.animation_id = None

    def ask_password(self, prompt):
        """Prompt user to input a password."""
        root = tk.Toplevel(self.master)
        root.title("Password")
        root.configure(bg="black")
        root.geometry("400x200")

        tk.Label(
            root,
            text=prompt,
            bg="black",
            fg="#00FF00",
            font=("Matrix", 14)
        ).pack(pady=10)

        password_entry = tk.Entry(root, show="*", font=("Arial", 14), bg="white", fg="black", width=30)
        password_entry.pack(pady=5)

        result = {"password": None}

        def on_submit():
            password = password_entry.get()
            if not password:
                messagebox.showwarning("Warning", "Password cannot be empty.")
            else:
                result["password"] = password
                root.destroy()

        password_entry.bind("<Return>", lambda event: on_submit())
        tk.Button(
            root,
            text="SUBMIT",
            command=on_submit,
            bg="black",
            fg="#00FF00",
            font=("Matrix", 14),
            relief="ridge"
        ).pack(pady=10)

        root.grab_set()
        root.wait_window()
        return result["password"]

    def specify_existing_vault(self):
        """Specify an existing vault."""
        file_path = filedialog.askopenfilename(title="Select Existing Vault", filetypes=[("ZIP files", "*.zip")])
        if file_path:
            password = self.ask_password("Enter the vault password:")
            if password:
                self.vault.set_vault(file_path, password)
                try:
                    if self.vault.validate_vault():
                        messagebox.showinfo("Success", "Vault opened successfully!")
                        self.cleanup_and_proceed()
                    else:
                        messagebox.showerror("Error", "Invalid password or vault.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to validate vault: {e}")

    def create_new_vault(self):
        """Create a new vault."""
        file_path = filedialog.asksaveasfilename(
            title="Create New Vault",
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")]
        )
        if file_path:
            password = self.ask_password("Enter a password for the new vault:")
            if password:
                self.vault.set_vault(file_path, password)
                try:
                    self.vault.create_vault()
                    messagebox.showinfo("Success", "Vault created successfully!")
                    self.cleanup_and_proceed()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create vault: {e}")

    def cleanup_and_proceed(self):
        """Cleanup the current window and proceed."""
        self.stop_animation()
        self.master.update_idletasks()
        self.master.quit()
        self.on_vault_success(self.vault)
