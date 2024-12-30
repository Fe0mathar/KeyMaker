import subprocess
import threading
import queue
import os
import time


class NeoCliManager:
    def __init__(self, cli_path, console_log=None):
        """
        Initialize NeoCliManager.

        :param cli_path: Path to the Neo-CLI executable.
        :param console_log: Function to log messages to the program console.
        """
        self.cli_path = cli_path
        self.process = None
        self.output_queue = queue.Queue()
        self.output_lines = []  # Stores CLI output for reference
        self.console_log = console_log or self._default_console_log  # Function to log to console
        self.awaiting_password = False  # Tracks if CLI is awaiting a password input

    @staticmethod
    def _default_console_log(message):
        """Default console log function if none is provided."""
        print(f"[NeoCliManager] {message}")

    def start_cli(self):
        """Start the Neo-CLI process."""
        try:
            self.process = subprocess.Popen(
                [self.cli_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            threading.Thread(target=self._read_output, daemon=True).start()
        except Exception as e:
            raise RuntimeError(f"Error starting Neo-CLI: {e}")

    def _read_output(self):
        """Read output from Neo-CLI and store it in the output queue."""
        try:
            for line in iter(self.process.stdout.readline, ""):
                self.output_queue.put(line)
                self.output_lines.append(line.strip())

                # Debugging: Capture CLI prompts or password-related events
                if "password:" in line.lower():
                    self.awaiting_password = True
        except Exception as e:
            self.output_queue.put(f"Error reading Neo-CLI output: {e}")

    def execute_cli_command(self, command, timeout=10):
        """Send a command to Neo-CLI and return the response."""
        try:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError("Neo-CLI process is not running.")

            # Send the command
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

            # Wait for response
            response = self._collect_output(timeout)

            # Add command and response to output lines for visibility
            self.output_lines.append(f"> {command}")
            self.output_lines.extend(response.splitlines())

            return response
        except Exception as e:
            return f"Error executing CLI command '{command}': {e}"

    def _collect_output(self, timeout):
        """Collect output from Neo-CLI with a timeout."""
        output = []
        start_time = time.time()
        prompt_detected = False

        while time.time() - start_time < timeout:
            try:
                line = self.output_queue.get(timeout=1)
                output.append(line.strip())

                # Detect CLI prompt and ensure no lines are missed
                if "neo>" in line:
                    if prompt_detected:
                        break
                    prompt_detected = True
            except queue.Empty:
                break

        # Handle potential incomplete output
        if not prompt_detected:
            output.append("CLI Output: Incomplete response or timeout.")

        return "\n".join(output)

    def connect_wallet(self, wallet_path):
        """
        Open a wallet in Neo-CLI using the given path.

        :param wallet_path: Path to the wallet JSON file.
        :return: A status message indicating the result of the operation.
        """
        try:
            # Send the open wallet command
            command = f"open wallet {wallet_path}"
            response = self.execute_cli_command(command)
            return response
        except Exception as e:
            return f"Error opening wallet: {e}"

    def send_password(self, password):
        """
        Send the password to Neo-CLI after the open wallet command.

        :param password: The wallet password.
        :return: CLI response to the password input.
        """
        try:
            response = self.execute_cli_command(password)
            self.awaiting_password = False  # Reset the password awaiting flag
            return response
        except Exception as e:
            return f"Error sending password: {e}"

    def is_running(self):
        """Check if Neo-CLI is running."""
        return self.process is not None and self.process.poll() is None

    def stop(self):
        """Stop the Neo-CLI process."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None

    def cleanup(self):
        """
        Perform cleanup tasks, such as stopping Neo-CLI and clearing internal queues.
        """
        self.stop()
        self.output_queue = queue.Queue()  # Clear the output queue
        self.output_lines = []  # Reset the output lines

    def execute_custom_command(self, command, timeout=10):
        """Send a custom command to Neo-CLI."""
        return self.execute_cli_command(command, timeout)

    def get_output_lines(self):
        """
        Get a snapshot of the current CLI output for display.

        :return: Last 10 lines of output.
        """
        return self.output_lines[-10:]  # Return the last 10 lines for context
