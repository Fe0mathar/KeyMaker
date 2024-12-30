import os
import tkinter as tk
from threading import Lock
from random import choice, randrange, random, randint
from PIL import Image, ImageDraw, ImageFont, ImageTk
import time
import textwrap
import math

###############################################################################
# Symbol
###############################################################################

class Symbol:
    """
    A single character in the matrix columns (green) or console text (white).
    If system_failure_in_progress => partial red.
    If reverse_in_progress => interpret ratio backwards => symmetrical color path.
    """
    def __init__(self, x, y, speed, canvas, font_path, is_console=False):
        self.x = x
        self.y = y
        self.speed = speed
        self.canvas = canvas

        # console => white, else random green
        if is_console:
            self.color = (255, 255, 255)
        else:
            g_val = randint(160, 255)
            self.color = (0, g_val, 0)

        self.alpha = 0
        self.text_id = None
        self.value = self.random_katakana()

        # Fallback font
        if not os.path.exists(font_path):
            font_path = "arial.ttf"
        self.font = ImageFont.truetype(font_path, 20)

        # partial red
        self.max_red_ratio = 0.5 + 0.5 * random()
        self.is_tip = False

        # shining
        self.is_shining = False
        self.blink_phase = 0.0
        self.blink_freq = 0.5 + random()  # [0.5..1.5]
        self.blink_phase_off = 2.0 * math.pi * random()

    def random_katakana(self):
        base = 0x30A0
        offset = randrange(96)
        return chr(base + offset)

    def generate_symbols(self):
        syms = []
        for _ in range(10):
            b = 0x30A0
            offset = randrange(96)
            syms.append(chr(b + offset))
        return syms

    def draw(self):
        matrix_error_mode = getattr(self.canvas, "matrix_error_mode", False)
        stop_y_movement = getattr(self.canvas, "stop_y_movement", False)
        fail_ratio = getattr(self.canvas, "system_failure_ratio", 0.0)
        reverse_in_progress = getattr(self.canvas, "reverse_in_progress", False)

        # if not freeze => fall
        if not (matrix_error_mode and stop_y_movement):
            if self.y >= self.canvas.winfo_height():
                self.y = -20
            else:
                self.y += self.speed

        if self.text_id:
            self.canvas.delete(self.text_id)

        # fade in alpha
        if self.alpha < 255:
            self.alpha += 15
            if self.alpha > 255:
                self.alpha = 255

        # build an RGBA image
        img = Image.new("RGBA", (30, 30), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if matrix_error_mode:
            exponent = 1.7
            if not reverse_in_progress:
                # forward => ratio^exponent
                R = fail_ratio ** exponent
            else:
                # reverse => 1 - ratio^exponent
                R = 1.0 - (fail_ratio ** exponent)

            def blend(a, b, rv):
                return int(a * (1 - rv) + b * rv)

            base_c = self.color
            red_target = (int(255 * self.max_red_ratio), 0, 0)
            rc = (
                blend(base_c[0], red_target[0], R),
                blend(base_c[1], red_target[1], R),
                blend(base_c[2], red_target[2], R),
            )
            final_col = self._apply_shining(rc)
        else:
            final_col = self._apply_shining(self.color)

        alph = int(min(255, self.alpha))
        c_blend = tuple(int(c * (alph / 255)) for c in final_col)

        draw.text((0, 0), self.value, font=self.font, fill=c_blend)
        self.tk_img = ImageTk.PhotoImage(img)
        self.text_id = self.canvas.create_image(
            self.x, self.y, image=self.tk_img, anchor="nw"
        )

    def _apply_shining(self, base_color):
        if self.is_tip or self.is_shining:
            self.blink_phase += 0.2 * self.blink_freq
            amp = 0.7 + 0.3 * math.sin(self.blink_phase + self.blink_phase_off)
            rc = int(base_color[0] * amp)
            gc = int(base_color[1] * amp)
            bc = int(base_color[2] * amp)
            rc = max(0, min(255, rc))
            gc = max(0, min(255, gc))
            bc = max(0, min(255, bc))
            return (rc, gc, bc)
        return base_color


###############################################################################
# TransformingSymbol
###############################################################################
class TransformingSymbol(Symbol):
    """
    Flickers from random ASCII => final_char => partial red if system failure
    fade-out => random green Katakana
    """
    def __init__(self, x, y, speed, canvas, final_char, font_path, is_console=False):
        super().__init__(x, y, speed, canvas, font_path, is_console=is_console)
        self.final_char = final_char
        self.transform_steps = 35
        self.transformed = False
        self.fading_out = False

    def generate_readable_symbols(self):
        ascii_syms = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
        return [choice(ascii_syms) for _ in range(10)]

    def draw(self):
        if getattr(self.canvas, "matrix_error_mode", False):
            super().draw()
            return

        if not self.transformed and self.transform_steps > 0:
            syms = self.generate_readable_symbols()
            self.value = choice(syms)
            self.transform_steps -= 1
        elif not self.transformed:
            self.value = self.final_char
            self.transformed = True
        elif self.fading_out:
            self.alpha -= 10
            if self.alpha < 0:
                self.alpha = 0
            syms = super().generate_symbols()
            self.value = choice(syms)

        super().draw()


###############################################################################
# ConsoleText
###############################################################################
class ConsoleText:
    def __init__(self, canvas, text, font_path, duration_ms=12000):
        self.canvas = canvas
        self.text = text
        self.font_path = font_path
        self.duration = duration_ms / 1000.0
        self.active = True
        self.start_time = None
        self.symbols = []

        max_chars = 29
        lines = textwrap.fill(text, max_chars).split("\n")

        x_offset = (canvas.winfo_width() - len(lines[0]) * 20) // 2
        if x_offset < 0:
            x_offset = 0
        y_offset = -20 * len(lines)
        row_spacing = 40

        for j, row in enumerate(lines):
            for i, ch in enumerate(row):
                ts = TransformingSymbol(
                    x_offset + i * 20,
                    y_offset + j * row_spacing,
                    speed=2.5,
                    canvas=self.canvas,
                    final_char=ch,
                    font_path=self.font_path,
                    is_console=True,
                )
                if random() < 0.1:
                    ts.is_shining = True
                self.symbols.append(ts)

    def draw(self):
        if self.start_time is None:
            self.start_time = time.time()

        if getattr(self.canvas, "system_failure_frozen", False):
            self.active = False
            return

        e = time.time() - self.start_time
        fade_start = self.duration - 2.0

        for sym in self.symbols:
            if e > fade_start:
                sym.fading_out = True
            sym.draw()

        if e > self.duration:
            self.active = False


###############################################################################
# SymbolColumn
###############################################################################
class SymbolColumn:
    def __init__(self, x, canvas, font_path):
        self.canvas = canvas
        self.speed = randrange(3, 7)
        tmp_syms = []

        count = randrange(8, 24)
        for i in range(count):
            y = -20 * (i + 1)
            s = Symbol(x, y, self.speed, canvas, font_path, is_console=False)
            if random() < 0.1:
                s.is_shining = True
            tmp_syms.append(s)

        tmp_syms.reverse()
        if tmp_syms:
            bottom = tmp_syms[0]
            bottom.is_tip = True
            bottom.max_red_ratio = 1.0
        tmp_syms.reverse()

        self.symbols = tmp_syms

    def draw(self):
        for sym in self.symbols:
            sym.draw()


###############################################################################
# Matrix
###############################################################################
class Matrix:
    """
    60 FPS aggregator + immediate system failure blinking.

    aggregator:
      * flush => 3 lines or 3s
      * each line => (#wrapped_rows * 2s) gap => reduce overlap

    system failure:
      * box blinking from t=0 every 0.5s
      * 2..5 => freeze Y => partial red ratio=0..1^1.7 => skip oranges
      * 5+ => ratio=1 => indefinite flicker
      or until user triggers stop => revert red->green
    """

    def __init__(self, canvas, width, height, font_path="F:/KeyMaker/MS_Mincho.ttf"):
        self.canvas = canvas
        self.width = width
        self.height = height

        if not os.path.exists(font_path):
            font_path = "arial.ttf"
        self.font_path = font_path

        # SHIFT columns by removing leftmost, adding on right => total 27 columns
        col_count = 27
        col_spacing = 20
        start_x = 20
        self.columns = [
            SymbolColumn(x, self.canvas, self.font_path)
            for x in range(start_x, start_x + col_count*col_spacing, col_spacing)
        ]

        self.console_texts = []
        self.running = False

        self.aggregator_lines = []
        self.aggregator_start = None
        self.aggregator_duration = 3.0
        self.aggregator_size_limit = 3
        self.base_per_row_gap = 2.0
        self.next_line_time = time.time()

        # system failure
        self.canvas.matrix_error_mode = False
        self.canvas.system_failure_ratio = 0.0
        self.canvas.system_failure_frozen = False
        self.canvas.stop_y_movement = False
        self.canvas.reverse_in_progress = False  # for symmetrical revert

        self.system_failure_in_progress = False
        self.system_failure_start = None

        self.lock = Lock()

    def queue_message(self, text: str):
        lw = text.lower()
        if "error" in lw or "wrong password" in lw:
            self.start_system_failure()
        elif self.system_failure_in_progress:
            self.stop_system_failure()
        else:
            with self.lock:
                self.aggregator_lines.append(text)
                self.aggregator_start = time.time()
        print("Matrix => queued:", text)

    def start_system_failure(self):
        if not self.system_failure_in_progress:
            print("Matrix: system failure triggered!")
            self.system_failure_in_progress = True
            self.canvas.matrix_error_mode = True
            self.canvas.system_failure_ratio = 0.0
            self.canvas.reverse_in_progress = False
            self.canvas.system_failure_frozen = False
            self.canvas.stop_y_movement = False
            self.system_failure_start = time.time()

    def stop_system_failure(self):
        """
        Immediately end animate_failure => remove blinking box => revert red->green
        """
        print("Matrix: stopping system failure => revert color to green now.")
        self.system_failure_in_progress = False
        self.canvas.delete("system_failure_box")
        self.canvas.stop_y_movement = True
        self.revert_rainfall_to_green()

    def revert_rainfall_to_green(self):
        """
        same exponent path => ratio= 0..1 => interpret as 1-ratio^exponent
        so it looks symmetrical to forward path
        -- 50% faster => 1500 ms instead of 3000
        """
        self.canvas.reverse_in_progress = True
        duration = 1500  # was 3000, now 50% faster
        steps = 30
        step_dt = duration // steps

        def step_rev(i):
            frac = i / float(steps)
            self.canvas.system_failure_ratio = frac

            if i < steps:
                self.canvas.after(step_dt, step_rev, i + 1)
            else:
                # done => normal
                self.canvas.system_failure_ratio = 0.0
                self.canvas.matrix_error_mode = False
                self.canvas.system_failure_frozen = False
                self.canvas.stop_y_movement = False
                self.canvas.reverse_in_progress = False
                print("Rainfall => fully back normal (red->green reversed).")

        step_rev(0)

    def start(self):
        print("Matrix: start aggregator + immediate system failure blinking @60FPS.")
        self.running = True
        self.update()

    def stop(self):
        print("Matrix: stopping.")
        self.running = False

    def update(self):
        if not self.running:
            return

        if not self.canvas.system_failure_frozen:
            for col in self.columns:
                col.draw()

        for ct in self.console_texts[:]:
            ct.draw()
            if not ct.active:
                self.console_texts.remove(ct)

        if self.system_failure_in_progress:
            self.animate_failure()
        else:
            self.check_aggregator()

        self.canvas.after(16, self.update)

    def animate_failure(self):
        e = time.time() - (self.system_failure_start or 0)
        self.draw_system_failure_box(e)

        if e < 2.0:
            self.canvas.system_failure_ratio = 0.0
            self.canvas.stop_y_movement = False
            self.canvas.system_failure_frozen = False
        elif e < 5.0:
            self.canvas.stop_y_movement = True
            ratio = (e - 2.0) / 3.0
            if ratio > 1.0:
                ratio = 1.0
            self.canvas.system_failure_ratio = ratio
            self.canvas.system_failure_frozen = False
        else:
            # indefinite final partial red flicker
            self.canvas.stop_y_movement = True
            self.canvas.system_failure_ratio = 1.0
            self.canvas.system_failure_frozen = False

    def draw_system_failure_box(self, e):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        bw = 400
        bh = 100
        x1 = (w - bw) // 2
        y1 = (h - bh) // 2
        x2 = x1 + bw
        y2 = y1 + bh

        self.canvas.delete("system_failure_box")

        half_cycle = int(e // 0.5)
        visible = (half_cycle % 2 == 0)
        if visible:
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="black",
                outline="#00FF00",
                width=4,
                tags="system_failure_box",
            )
            self.canvas.create_text(
                (x1 + x2) // 2,
                (y1 + y2) // 2,
                text="SYSTEM FAILURE",
                fill="#00FF00",
                font=("Courier", 24, "bold"),
                tags="system_failure_box",
            )

    def check_aggregator(self):
        if self.system_failure_in_progress:
            return
        with self.lock:
            if self.aggregator_lines:
                c = len(self.aggregator_lines)
                if c >= self.aggregator_size_limit:
                    self.flush_aggregator()
                else:
                    if (time.time() - (self.aggregator_start or 0)) >= self.aggregator_duration:
                        self.flush_aggregator()

    def flush_aggregator(self):
        lines = self.aggregator_lines[:]
        self.aggregator_lines.clear()
        self.aggregator_start = None

        now_time = time.time()
        for line in lines:
            row_count = self.get_wrapped_line_count(line)
            line_gap = row_count * self.base_per_row_gap

            def show_line(ln=line):
                if not self.system_failure_in_progress:
                    ctext = ConsoleText(
                        self.canvas, ln, self.font_path, duration_ms=12000
                    )
                    self.console_texts.append(ctext)
                print(f"Matrix: displayed => {ln} (rows={row_count}, gap={line_gap}s)")

            now = time.time()
            if now < self.next_line_time:
                wait_ms = int((self.next_line_time - now) * 1000)
            else:
                wait_ms = 0

            self.canvas.after(wait_ms, show_line)
            self.next_line_time = max(self.next_line_time, now) + line_gap

        print("Matrix: aggregator flush =>", lines)

    def get_wrapped_line_count(self, line):
        max_chars = 29  # matching the wrap length in ConsoleText
        wrapped = textwrap.fill(line, max_chars).split("\n")
        return len(wrapped)
