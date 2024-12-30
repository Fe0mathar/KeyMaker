import json
import time
import os
import openai
from openai import OpenAIError
import threading
from difflib import get_close_matches
import pyzipper

class AIEngine:
    """
    A more extensive AI Engine (Seraph) integrated with GPT-4.

    Key Points:
      - Recognized KeyMaker commands run regardless of Morpheus status.
      - Unrecognized text => GPT fallback only if console.morpheus_unlocked == True 
        AND we have a valid ChatGPT API Key in memory.
      - recheck_api_keys() can be called post-final Morpheus unlock to refresh the GPT key.
    """

    def __init__(
        self,
        console,
        config_file="F:/KeyMaker/seraph.json",
        morpheus_wallet_zip_path=None,
        morpheus_wallet_password=None
    ):
        """
        :param console: 
            The ConsoleWindow instance for logging output and bridging commands.
        :param config_file:
            Path to a JSON with command mappings, synonyms, etc.
        :param morpheus_wallet_zip_path:
            Path to the Morpheus .zip containing 'api_keys.txt'
        :param morpheus_wallet_password:
            Password (bytes or str) to decrypt that .zip
        """
        self.console = console
        self.config_file = config_file
        self.morpheus_wallet_zip_path = morpheus_wallet_zip_path

        # Convert password if needed
        if isinstance(morpheus_wallet_password, str):
            self.morpheus_wallet_zip_password = morpheus_wallet_password.encode()
        else:
            self.morpheus_wallet_zip_password = morpheus_wallet_password

        # Load config data
        self.config_data = self.load_config(config_file)

        # Extract KeyMaker commands + synonyms
        cmd_map = self.config_data.get("COMMAND_MAPPINGS", {})
        self.commands = {
            item["command"]: item["synonyms"]
            for item in cmd_map.get("commands", [])
        }

        # Simple responses
        self.acknowledgments = cmd_map.get("acknowledgments", [])
        self.greetings = cmd_map.get("greetings", [])
        self.farewells = cmd_map.get("farewells", [])

        # Additional config sets
        self.responses = self.config_data.get("RESPONSES", {})
        self.rules = self.config_data.get("RULES", {})
        self.settings = self.config_data.get("SETTINGS", {})

        # GPT usage
        self.openai_api_key = None
        self.twitter_keys = {}

        # Attempt initial load of GPT key if .zip path/password are already known
        self.load_api_keys_from_morpheus()

        # AIEngine states
        self.last_activity_time = time.time()
        self.current_context = None
        self.command_in_progress = False

        # Keep a conversation for GPT fallback
        self.conversation_history = []

    def load_config(self, config_file):
        """Load JSON from disk, handle missing or parse errors gracefully."""
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                self.console.log(
                    f"SERAPH: Error parsing config file: {e}",
                    tag="seraph",
                    color="#FFFF55"
                )
                return {}
        else:
            self.console.log(
                f"SERAPH: Config file not found: {config_file}",
                tag="seraph",
                color="#FFFF55"
            )
            return {}

    def load_api_keys_from_morpheus(self):
        """
        Attempt to read 'api_keys.txt' from Morpheus zip. 
        If 'ChatGPT API Key:' is found, set self.openai_api_key & openai.api_key.
        """
        if not self.morpheus_wallet_zip_path or not self.morpheus_wallet_zip_password:
            # The user requested no log lines about skipping initial load
            return

        try:
            with pyzipper.AESZipFile(self.morpheus_wallet_zip_path, 'r',
                                     encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.morpheus_wallet_zip_password)
                if "api_keys.txt" in zf.namelist():
                    data = zf.read("api_keys.txt").decode("utf-8")
                    self._parse_api_keys(data)
                else:
                    # The user requested no lines for missing 'api_keys.txt'
                    pass
        except Exception as e:
            self.console.log(
                f"SERAPH: Error reading API keys from Morpheus zip: {e}",
                tag="seraph",
                color="#FF0000"
            )

    def recheck_api_keys(self):
        """
        After user fully unlocks Morpheus, call this again 
        so we definitely parse 'api_keys.txt' with the known .zip & pass.
        """
        if not self.morpheus_wallet_zip_path or not self.morpheus_wallet_zip_password:
            # The user requested no lines about skipping re-check if missing
            return

        try:
            with pyzipper.AESZipFile(self.morpheus_wallet_zip_path, 'r',
                                     encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(self.morpheus_wallet_zip_password)
                if "api_keys.txt" in zf.namelist():
                    data = zf.read("api_keys.txt").decode("utf-8")
                    self._parse_api_keys(data)
                else:
                    # user doesn't want logs about missing 'api_keys.txt'
                    pass
        except Exception as e:
            self.console.log(
                f"SERAPH: Error re-checking keys from Morpheus zip: {e}",
                tag="seraph",
                color="#FF0000"
            )

    def _parse_api_keys(self, raw_text):
        """
        Given the raw text of 'api_keys.txt', parse lines for 'ChatGPT API Key:' etc.
        """
        for line in raw_text.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                k = key.strip().lower()
                v = val.strip()
                if k == "chatgpt api key":
                    self.openai_api_key = v
                    openai.api_key = v  # set globally
                elif k.startswith("twitter "):
                    self.twitter_keys[k] = v

    # ---------------------------------------------------------------------
    # The main "respond_to_query" - user text
    # ---------------------------------------------------------------------
    def respond_to_query(self, user_input):
        """
        1) If recognized greeting/farewell => short SERAPH reply
        2) If recognized KeyMaker command => pass to console
        3) Otherwise => if console.morpheus_unlocked => GPT fallback (if key), else offline message
        """
        if self.command_in_progress:
            return
        self.command_in_progress = True

        try:
            user_input = self.normalize_input(user_input)

            # 1) Check simple (greetings, farewells, etc.)
            if self.check_simple_responses(user_input):
                return

            # 2) Check KeyMaker command
            recognized_cmd = self.is_predefined_command(user_input)
            if recognized_cmd:
                self.console.log(
                    f"SERAPH: Executing predefined command: {recognized_cmd}",
                    tag="seraph",
                    color="#FFFF55"
                )
                self.console.handle_ai_command(recognized_cmd)
                return

            # 3) Not recognized => check Morpheus
            if not getattr(self.console, "morpheus_unlocked", False):
                self.console.log(
                    "OPERATOR: Seraph is offline until Morpheus wallet is connected // Command not recognized",
                    tag="operator",
                    color="#00FF00"
                )
                return

            # If unlocked => GPT fallback
            self.gpt_fallback(user_input)

        finally:
            self.command_in_progress = False

    def normalize_input(self, text):
        """Remove punctuation, force lowercase, etc., if configured."""
        if self.settings.get("input_normalization", {}).get("remove_punctuation", True):
            text = ''.join(c for c in text if c.isalnum() or c.isspace() or c in ":\\/.-")
        if self.settings.get("input_normalization", {}).get("lowercase_inputs", True):
            text = text.lower()
        return text.strip()

    def check_simple_responses(self, text):
        """
        If text in greetings/farewells/ack => short SERAPH message
        """
        if text in self.greetings:
            greet_msg = self.responses.get("greeting", "Hello there! How can I assist?")
            self.console.log(f"SERAPH: {greet_msg}", tag="seraph", color="#FFFF55")
            return True

        if text in self.farewells:
            bye_msg = self.responses.get("farewell", "Goodbye! Feel free to return anytime.")
            self.console.log(f"SERAPH: {bye_msg}", tag="seraph", color="#FFFF55")
            return True

        if text in self.acknowledgments:
            ack_msg = self.responses.get("acknowledgment", "You're welcome! Any other instructions?")
            self.console.log(f"SERAPH: {ack_msg}", tag="seraph", color="#FFFF55")
            return True

        return False

    def is_predefined_command(self, text):
        """If user_input matches a KeyMaker command or synonyms => return that command."""
        for cmd, synonyms in self.commands.items():
            if text == cmd or text in synonyms:
                return cmd
        return None

    def gpt_fallback(self, user_input):
        """
        For unrecognized text => GPT fallback if openai_api_key is set.
        Otherwise => "No GPT key" message.
        """
        if not self.openai_api_key:
            self.console.log(
                "SERAPH: No GPT-4 API key set; can't provide an intelligent answer.",
                tag="seraph",
                color="#FFFF55"
            )
            return

        self.add_message("user", user_input)
        reply = self.interact_with_gpt_conversational()
        self.console.log(f"SERAPH: {reply}", tag="seraph", color="#FFFF55")
        self.add_message("assistant", reply)

    def add_message(self, role, content):
        """
        Keep a conversation memory for GPT usage
        """
        self.conversation_history.append({"role": role, "content": content})
        max_hist = self.settings.get("max_gpt_history", 10)
        if len(self.conversation_history) > max_hist:
            self.conversation_history.pop(0)

    def interact_with_gpt_conversational(self):
        """Send entire conversation to GPT-4, get a reply."""
        try:
            openai.api_key = self.openai_api_key
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are Seraph, an advanced AI from the Matrix, guiding NEO calmly."
                    }
                ] + self.conversation_history,
                max_tokens=300,
                temperature=0.7
            )
            return response["choices"][0]["message"]["content"].strip()
        except OpenAIError as e:
            self.console.log(f"SERAPH: OpenAI Error: {str(e)}", tag="seraph", color="#FF0000")
            return "I encountered an OpenAI error. Please try again later."
        except Exception as e:
            self.console.log(f"SERAPH: Unexpected error: {str(e)}", tag="seraph", color="#FF0000")
            return "I encountered an unexpected error while calling GPT-4."
