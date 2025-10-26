import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
import sys
from math import inf
import traceback
from pathlib import Path

try:
    from PIL import Image, ImageTk

    PILLOW_INSTALLED = True
except ImportError:
    PILLOW_INSTALLED = False

def get_application_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parent


SCRIPT_DIR = get_application_path()
DATA_FILE = SCRIPT_DIR / "speed_run_records.json"
RUN_COMPLETE_STAGES = 10

DEFAULT_DATA = {
    "currentStage": "ECHOES",
    "currentSeason": 4,
    "seasons": {
        "ECHOES": {},
        "ETERNITY": {}
    },
    "config": {
        "background_color": "#1a1a2e",
        "frame_color": "#0a0a1a",
        "highlight_color": "#ffb703",
        "pb_split_color": "#34d399",
        "dream_split_color": "#00ffff",
        "image_path": r"issakis.jpg",
        "image_opacity": 0.2,
        "watermark_text": "Speed Tracker by White Claws LLC",
        "watermark_font_size": 8,
        "text_color": "#FFFFFF"
    }
}


def parse_time_input(input_str):
    try:
        if '.' in input_str:
            return float(input_str)

        s = str(int(input_str))
    except ValueError:
        return 0

    num = int(s)

    if len(s) == 3:
        minutes = int(s[0])
        seconds = int(s[1:])
        return (minutes * 60) + seconds
    elif len(s) >= 4:
        minutes = int(s[:-2])
        seconds = int(s[-2:])
        return (minutes * 60) + seconds
    else:
        return num


def format_time(total_seconds):
    if total_seconds == inf:
        return "---"
    if total_seconds < 0:
        return f"-{format_time(abs(total_seconds))}"
    total_seconds = round(total_seconds, 2)
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    if seconds == int(seconds):
        seconds_str = f"{seconds:.1f}"
    else:
        seconds_str = f"{seconds:.2f}"

    if '.' in seconds_str:
        sec_int, sec_frac = seconds_str.split('.')
    else:
        sec_int, sec_frac = seconds_str, '0'
    return f"{minutes}:{sec_int.zfill(2)}.{sec_frac}"


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if "seasons" not in data:
                    old_pb = data.get("pbTotalTimeSeconds", "inf")
                    if old_pb == "inf":
                        old_pb = inf

                    migrated_data = DEFAULT_DATA.copy()
                    migrated_data["config"] = data.get("config", DEFAULT_DATA["config"].copy())
                    migrated_data["seasons"]["ECHOES"]["4"] = {
                        "pbTotalTimeSeconds": old_pb,
                        "pbRunTimes": data.get("pbRunTimes", []),
                        "bestSplits": data.get("bestSplits", {}),
                        "runCount": data.get("runCount", 0)
                    }

                    return migrated_data
                full_data = DEFAULT_DATA.copy()
                full_data.update(data)
                if "config" in data:
                    full_data["config"] = DEFAULT_DATA["config"].copy()
                    full_data["config"].update(data["config"])
                for stage in full_data["seasons"]:
                    for season in full_data["seasons"][stage]:
                        if full_data["seasons"][stage][season].get("pbTotalTimeSeconds") == "inf":
                            full_data["seasons"][stage][season]["pbTotalTimeSeconds"] = inf

                return full_data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            messagebox.showerror("Error",
                                 f"Could not load or parse records file. Starting with default data.\nError: {e}")
            return DEFAULT_DATA
    return DEFAULT_DATA


def save_data(data):
    save_data = json.loads(json.dumps(data))
    for stage in save_data["seasons"]:
        for season in save_data["seasons"][stage]:
            if save_data["seasons"][stage][season].get("pbTotalTimeSeconds") == inf:
                save_data["seasons"][stage][season]["pbTotalTimeSeconds"] = "inf"

    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = DATA_FILE.with_suffix('.json.tmp')
        with open(temp_file, 'w') as f:
            json.dump(save_data, f, indent=4)
        temp_file.replace(DATA_FILE)
        print(f"Data saved successfully to: {DATA_FILE}")

    except IOError as e:
        messagebox.showerror("Error", f"Could not save records file.\nPath: {DATA_FILE}\nError: {e}")
    except Exception as e:
        messagebox.showerror("Error", f"Unexpected error saving data: {e}")


class SpeedRunTrackerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Speed Run Tracker")

        if not PILLOW_INSTALLED:
            self.show_pillow_error()
            return

        self.data = load_data()
        self.config = self.data["config"]
        self.current_run = []
        self._ensure_season_exists()

        self.apply_config_colors()

        self.bg_image_tk = None
        self.bg_canvas = None

        self.setup_background_canvas()
        self.create_widgets_and_layout()

        self.render_all()
        self.master.after(100, self.resize_background_image)

    def _ensure_season_exists(self):
        stage = self.data["currentStage"]
        season = str(self.data["currentSeason"])

        if stage not in self.data["seasons"]:
            self.data["seasons"][stage] = {}

        if season not in self.data["seasons"][stage]:
            self.data["seasons"][stage][season] = {
                "pbTotalTimeSeconds": inf,
                "pbRunTimes": [],
                "bestSplits": {},
                "runCount": 0
            }

    def get_current_season_data(self):
        """Get the data for the currently selected stage and season."""
        stage = self.data["currentStage"]
        season = str(self.data["currentSeason"])
        return self.data["seasons"][stage][season]

    def show_pillow_error(self):
        error_msg = ("The Python Imaging Library (Pillow) is required to load and process the background image.\n\n"
                     "Please install it using: \n\n"
                     "pip install Pillow")
        messagebox.showerror("Dependency Missing", error_msg)
        self.master.destroy()

    def apply_config_colors(self):
        self.bg_color = self.config["background_color"]
        self.frame_color = self.config["frame_color"]
        self.text_color = self.config.get("text_color", "#FFFFFF")
        self.highlight_color = self.config["highlight_color"]
        self.pb_split_color = self.config.get("pb_split_color", "#34d399")
        self.dream_split_color = self.config.get("dream_split_color", "#00ffff")
        self.master.configure(bg=self.bg_color)

    def setup_background_canvas(self):
        self.bg_canvas = tk.Canvas(self.master, highlightthickness=0, bg=self.bg_color)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.master.bind("<Configure>", self.on_resize)
        self.image_item = None

    def load_background_image(self):
        if not PILLOW_INSTALLED:
            return

        image_path_str = self.config.get("image_path")
        if not image_path_str:
            return
        image_path = SCRIPT_DIR / image_path_str

        try:
            if not image_path.exists():
                image_path = Path(image_path_str)

            self.image_original = Image.open(image_path).convert("RGBA")
            self.resize_background_image()
        except FileNotFoundError:
            print(f"Warning: Image file not found at {image_path}. Please check config.")
            self.image_original = None
            self.img_tk = None
            messagebox.showerror("Image Error",
                                 f"Could not find image at {image_path}. Please check the path in 'speed_run_records.json'.")
            self.config["image_path"] = ""
            save_data(self.data)
            self.bg_canvas.delete("bg_img")
        except Exception as e:
            traceback.print_exc()
            print(f"Error loading background image: {e}")
            messagebox.showerror("Image Error",
                                 f"Could not load background image from '{image_path}'. Error: {e}")
            self.config["image_path"] = ""
            save_data(self.data)
            self.bg_canvas.delete("bg_img")

    def resize_background_image(self, event=None):
        if not PILLOW_INSTALLED or self.image_original is None:
            return

        try:
            w = self.bg_canvas.winfo_width()
            h = self.bg_canvas.winfo_height()
        except tk.TclError:
            return

        if w <= 1 or h <= 1:
            return

        original_w, original_h = self.image_original.size
        ratio = max(w / original_w, h / original_h)
        new_w, new_h = int(original_w * ratio), int(original_h * ratio)

        x_offset = (new_w - w) // 2
        y_offset = (new_h - h) // 2

        img_resized = self.image_original.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_cropped = img_resized.crop((x_offset, y_offset, x_offset + w, y_offset + h))

        opacity_level = self.config.get("image_opacity", 0.2)
        r, g, b = [int(self.config["background_color"][i:i + 2], 16)
                   for i in (1, 3, 5)]
        overlay_color = Image.new('RGBA', img_cropped.size, (r, g, b, int(255 * (1 - opacity_level))))
        img_final = Image.alpha_composite(img_cropped, overlay_color)

        self.img_tk = ImageTk.PhotoImage(img_final)

        if getattr(self, "image_item", None):
            self.bg_canvas.itemconfig(self.image_item, image=self.img_tk)
        else:
            self.image_item = self.bg_canvas.create_image(w // 2, h // 2, image=self.img_tk, anchor="center")

        self.bg_canvas.image_ref = self.img_tk  # prevent GC
        self.bg_canvas.tag_lower(self.image_item)
        self.bg_canvas.update_idletasks()

    def on_resize(self, event):
        if event.widget != self.master:
            return
        if getattr(self, "_resizing", False):
            return

        self._resizing = True
        self.master.after(80, self._apply_resized)  # redraw every 80 ms while resizing

    def _apply_resized(self):
        self.resize_background_image()
        self.update_widget_positions()
        self._resizing = False

    def update_widget_positions(self):
        w = self.bg_canvas.winfo_width()
        h = self.bg_canvas.winfo_height()

        if w <= 1 or h <= 1: return
        self.bg_canvas.delete("input_window")
        self.bg_canvas.create_window(w / 2, 40,
                                     window=self.input_frame,
                                     anchor=tk.N,
                                     tags="input_window")

        self.bg_canvas.delete("watermark_window")
        self.bg_canvas.create_window(w / 2, h - 3,
                                     window=self.watermark_label,
                                     anchor=tk.S,
                                     tags="watermark_window")
        main_y_start = 85
        main_y_end = h - 10
        main_height = main_y_end - main_y_start

        if main_height < 10: main_height = 10

        self.bg_canvas.delete("main_window")
        self.bg_canvas.create_window(w / 2, main_y_start,
                                     window=self.main_frame,
                                     anchor=tk.N,
                                     width=w - 20,
                                     height=main_height,
                                     tags="main_window")

    def create_widgets_and_layout(self):

        self.input_frame = tk.Frame(self.bg_canvas, bg=self.bg_color, padx=15, pady=5, bd=0, relief=tk.FLAT)
        self.input_label = tk.Label(self.input_frame, text="", bg=self.bg_color, fg=self.text_color,
                                    font=('Inter', 12, 'bold'), borderwidth=0, highlightthickness=0)
        self.input_label.pack(side=tk.LEFT, padx=5)

        self.time_input = tk.Entry(self.input_frame, width=10, font=('Inter', 14), justify='center',
                                   bg=self.frame_color, fg=self.highlight_color, insertbackground=self.text_color,
                                   borderwidth=0, highlightthickness=0)
        self.time_input.bind('<Return>', lambda event: self.add_time())
        self.time_input.pack(side=tk.LEFT, padx=10, ipady=2)
        self.add_button = tk.Button(self.input_frame, text="Add Stage 1", command=self.add_time,
                                    bg=self.highlight_color, fg=self.frame_color, font=('Inter', 12, 'bold'),
                                    activebackground=self.highlight_color, borderwidth=0, highlightthickness=0)
        self.add_button.pack(side=tk.LEFT, padx=10, ipady=2)
        tk.Button(self.input_frame, text="Re-read Config", command=self.refresh_config, bg="#0088AA", fg="white",
                  font=('Inter', 10), activebackground="#00AACC", borderwidth=0, highlightthickness=0).pack(
            side=tk.RIGHT, padx=(10, 5))
        tk.Button(self.input_frame, text="Wipe All PBs", command=self.confirm_wipe_all, bg="#dc2626", fg="white",
                  font=('Inter', 10), activebackground="#ef4444", borderwidth=0, highlightthickness=0).pack(
            side=tk.RIGHT, padx=(10, 5))
        self.end_run_button = tk.Button(self.input_frame, text="End Current Run", command=self.confirm_end_run,
                                        bg="#f59e0b", fg="white", font=('Inter', 10), activebackground="#fbbf24",
                                        borderwidth=0, highlightthickness=0)
        self.end_run_button.pack(side=tk.RIGHT)
        self.main_frame = tk.Frame(self.bg_canvas, bg=self.bg_color, borderwidth=0, highlightthickness=0)

        self.main_frame.grid_columnconfigure(0, weight=9)  # Current Run (Needs more space for diffs)
        self.main_frame.grid_columnconfigure(1, weight=5)  # Best Splits (Dream Run)
        self.main_frame.grid_columnconfigure(2, weight=5)  # PB Run
        self.main_frame.grid_rowconfigure(0, weight=1)

        current_run_frame = self.create_list_frame(self.main_frame, "Current Run", 0)

        self.stage_season_label = tk.Label(current_run_frame, text="", bg=self.bg_color,
                                           fg=self.highlight_color, font=('Inter', 11, 'bold'),
                                           justify='center', borderwidth=0, highlightthickness=0)
        self.stage_season_label.grid(row=1, column=0, sticky='ew', pady=(0, 2))

        self.run_count_label = tk.Label(current_run_frame, text="", bg=self.bg_color,
                                        fg=self.text_color, font=('Inter', 10), justify='center', borderwidth=0,
                                        highlightthickness=0)
        self.run_count_label.grid(row=2, column=0, sticky='ew', pady=(0, 5))
        self.current_total_label = tk.Label(current_run_frame, text="0:00.00", bg=self.bg_color,
                                            fg=self.highlight_color, font=('Inter', 24, 'bold'), justify='center',
                                            borderwidth=0, highlightthickness=0)
        self.current_total_label.grid(row=3, column=0, sticky='ew', pady=5)
        self.current_splits_list = self.create_listbox(current_run_frame, 4)

        dream_splits_frame = self.create_list_frame(self.main_frame, "All-Time Best Splits (Dream Run)", 1)
        self.dream_total_label = tk.Label(dream_splits_frame, text="0:00.00", bg=self.bg_color,
                                          fg=self.dream_split_color, font=('Inter', 18, 'bold'), justify='center',
                                          borderwidth=0, highlightthickness=0)
        self.dream_total_label.grid(row=1, column=0, sticky='ew', pady=5)
        self.dream_splits_list = self.create_listbox(dream_splits_frame, 2)
        dream_splits_frame.grid_rowconfigure(3, weight=1)

        pb_run_frame = self.create_list_frame(self.main_frame, "Personal Best Run", 2)
        self.pb_total_label = tk.Label(pb_run_frame, text="0:00.00", bg=self.bg_color, fg=self.pb_split_color,
                                       font=('Inter', 18, 'bold'), justify='center', borderwidth=0,
                                       highlightthickness=0)
        self.pb_total_label.grid(row=1, column=0, sticky='ew', pady=5)
        self.pb_splits_list = self.create_listbox(pb_run_frame, 2)
        pb_run_frame.grid_rowconfigure(3, weight=1)
        self.watermark_label = tk.Label(self.bg_canvas, text=self.config['watermark_text'], bg=self.bg_color,
                                        fg="#555555",
                                        font=('Inter', self.config['watermark_font_size']), borderwidth=0,
                                        highlightthickness=0)
        self.master.update_idletasks()
        self.update_widget_positions()

    def create_list_frame(self, parent_frame, title, column):
        frame = tk.Frame(parent_frame, bg=self.bg_color, borderwidth=0, highlightthickness=0)
        frame.grid(row=0, column=column, sticky='nsew', padx=5, pady=5)
        frame.grid_columnconfigure(0, weight=1)
        tk.Label(frame, text=title, bg=self.bg_color, fg=self.text_color, font=('Inter', 14, 'bold'), justify='center',
                 borderwidth=0, highlightthickness=0).grid(row=0, column=0, sticky='ew', pady=5)

        return frame

    def create_listbox(self, parent_frame, row):
        listbox = tk.Listbox(parent_frame,
                             bg=self.frame_color, fg=self.text_color,
                             font=('Inter', 11), selectmode=tk.NONE,
                             bd=0, relief=tk.FLAT, highlightthickness=0)
        listbox.grid(row=row, column=0, sticky='nsew')
        parent_frame.grid_rowconfigure(row, weight=1)
        return listbox

    def _update_dynamic_elements(self):
        current_stage = len(self.current_run)

        if current_stage < RUN_COMPLETE_STAGES:
            stage_num = current_stage + 1
            self.input_label.config(text=f"Enter TOTAL Time for Stage {stage_num}:")
            self.add_button.config(text=f"Add Stage {stage_num}", state=tk.NORMAL)
            self.time_input.config(state=tk.NORMAL)
            self.time_input.focus_set()
            self.end_run_button.config(state=tk.NORMAL)
        else:
            self.input_label.config(text="Run COMPLETE! End Run to finalize.")
            self.add_button.config(text="Finished", state=tk.DISABLED)
            self.time_input.delete(0, tk.END)
            self.time_input.config(state=tk.DISABLED)
            self.end_run_button.config(state=tk.NORMAL)  # Still allow ending/finalizing

    def refresh_config(self):
        old_config = self.config.copy()
        new_data = load_data()
        self.data = new_data
        self.config = self.data["config"]

        try:
            self.apply_config_colors()
            self.master.configure(bg=self.bg_color)

            if self.bg_canvas: self.bg_canvas.config(bg=self.bg_color)

            for widget in [self.input_frame, self.main_frame]:
                widget.config(bg=self.bg_color)

            for frame in self.main_frame.winfo_children():
                if isinstance(frame, tk.Frame):
                    for widget in frame.winfo_children():
                        if isinstance(widget, tk.Label):
                            widget.config(bg=self.bg_color, fg=self.text_color)

            self.current_total_label.config(fg=self.highlight_color)
            self.pb_total_label.config(fg=self.pb_split_color)
            self.dream_total_label.config(fg=self.dream_split_color)
            self.stage_season_label.config(fg=self.highlight_color)

            self.watermark_label.config(bg=self.bg_color, fg="#555555",
                                        text=self.config['watermark_text'],
                                        font=('Inter', self.config['watermark_font_size']))

            self.time_input.config(bg=self.frame_color, fg=self.highlight_color, insertbackground=self.text_color)
            self.current_splits_list.config(bg=self.frame_color, fg=self.text_color)
            self.pb_splits_list.config(bg=self.frame_color, fg=self.text_color)
            self.dream_splits_list.config(bg=self.frame_color, fg=self.text_color)

            self.load_background_image()
            self.render_all()

            messagebox.showinfo("Config Refreshed",
                                "Configuration (colors, image, watermark) has been reloaded from the JSON file.")

        except Exception as e:
            self.config = old_config
            self.data["config"] = old_config
            messagebox.showerror("Refresh Failed", f"Failed to apply new configuration settings. Error: {e}")

    def add_time(self):
        if len(self.current_run) >= RUN_COMPLETE_STAGES:
            messagebox.showwarning("Run Complete",
                                   "This run has reached the limit. Please 'End Current Run' to finalize and start a new one.")
            return

        input_value = self.time_input.get()
        self.time_input.delete(0, tk.END)

        if not input_value:
            return

        total_time_seconds = parse_time_input(input_value)
        stage_number = len(self.current_run) + 1

        previous_total_time = self.current_run[-1]["totalTimeSeconds"] if self.current_run else 0
        split_time_seconds = total_time_seconds - previous_total_time

        if split_time_seconds < 0:
            messagebox.showwarning("Warning",
                                   f"Total time ({format_time(total_time_seconds)}) cannot be less than the previous total time ({format_time(previous_total_time)}).")
            return

        self.current_run.append({
            "stage": stage_number,
            "totalTimeSeconds": total_time_seconds,
            "splitTimeSeconds": split_time_seconds,
            "input": input_value
        })
        self.check_and_update_dream_splits()
        self.render_all()

    def check_and_update_dream_splits(self):
        new_split_pbs = {}
        season_data = self.get_current_season_data()

        if not self.current_run:
            return

        for item in self.current_run:
            stage_key = str(item["stage"])
            existing_best_split = season_data["bestSplits"].get(stage_key, inf)

            # Use a slight tolerance here to ensure equal times are not considered worse
            if item["splitTimeSeconds"] < existing_best_split - 0.001:
                season_data["bestSplits"][stage_key] = item["splitTimeSeconds"]
                new_split_pbs[stage_key] = True
        if new_split_pbs:
            save_data(self.data)

    def render_all(self):
        self.watermark_label.config(text=self.config['watermark_text'])
        season_data = self.get_current_season_data()

        # Update stage/season display
        stage = self.data["currentStage"]
        season = self.data["currentSeason"]
        self.stage_season_label.config(text=f"{stage} - Season {season}")

        self.run_count_label.config(text=f"Runs: {season_data['runCount']}", fg=self.text_color)
        self.render_current_run()
        self.render_dream_splits()
        self.render_pb_run()

    def render_current_run(self):
        self.current_splits_list.delete(0, tk.END)
        season_data = self.get_current_season_data()

        self._update_dynamic_elements()

        if not self.current_run:
            self.current_total_label.config(text="0:00.00", fg=self.highlight_color)
            self.current_splits_list.insert(tk.END, "--- Enter the first time to begin a run ---")
            self.current_splits_list.itemconfig(0, fg=self.text_color)
            return

        last_total_time = self.current_run[-1]["totalTimeSeconds"]
        self.current_total_label.config(text=format_time(last_total_time))

        for item in self.current_run:
            stage_key = str(item["stage"])
            pb_split = season_data["bestSplits"].get(stage_key, inf)
            is_pb_split = item["splitTimeSeconds"] < pb_split + 0.001

            split_str = f"S{item['stage']}: SPLIT: {format_time(item['splitTimeSeconds'])} | TOTAL: {format_time(item['totalTimeSeconds'])}"
            diff = item["splitTimeSeconds"] - pb_split

            if is_pb_split and diff < 0.001:
                split_str += " (NEW BEST)"
            else:
                color = "#dc2626" if diff > 0.001 else "#f59e0b"  # Red for slower, Amber for close/slightly faster
                sign = "+" if diff > 0 else ""
                diff_str = f"({sign}{format_time(abs(diff))})"
                split_str += f" vs Dream: {diff_str}"

            self.current_splits_list.insert(tk.END, split_str)
            idx = self.current_splits_list.size() - 1
            self.current_splits_list.itemconfig(idx, fg=self.text_color)
            if item["splitTimeSeconds"] <= pb_split + 0.001:
                self.current_splits_list.itemconfig(idx, fg=self.dream_split_color)

    def render_dream_splits(self):
        self.dream_splits_list.delete(0, tk.END)
        season_data = self.get_current_season_data()
        best_splits = season_data["bestSplits"]

        if not best_splits:
            self.dream_total_label.config(text="0:00.00")
            self.dream_splits_list.insert(tk.END, "--- No Dream Splits recorded yet ---")
            self.dream_splits_list.itemconfig(0, fg=self.text_color)
            return
        dream_total_time = 0
        sorted_stages = sorted(best_splits.keys(), key=lambda x: int(x))

        for stage_key in sorted_stages:
            split_time = best_splits[stage_key]
            dream_total_time += split_time

            line = f"S{stage_key}: SPLIT: {format_time(split_time)}"
            self.dream_splits_list.insert(tk.END, line)
            idx = self.dream_splits_list.size() - 1
            self.dream_splits_list.itemconfig(idx, fg=self.dream_split_color)
        self.dream_total_label.config(text=format_time(dream_total_time))

    def render_pb_run(self):
        self.pb_splits_list.delete(0, tk.END)
        season_data = self.get_current_season_data()
        pb_times = season_data["pbRunTimes"]

        self.pb_total_label.config(text=format_time(season_data["pbTotalTimeSeconds"]))

        if not pb_times:
            self.pb_splits_list.insert(tk.END, "--- No Personal Best run recorded ---")
            self.pb_splits_list.itemconfig(0, fg=self.text_color)
            return

        previous_pb_time = 0
        for index, pb_total_time in enumerate(pb_times):
            stage_number = index + 1
            pb_run_split = pb_total_time - previous_pb_time
            previous_pb_time = pb_total_time

            line = f"S{stage_number}: SPLIT: {format_time(pb_run_split)} | TOTAL: {format_time(pb_total_time)}"

            self.pb_splits_list.insert(tk.END, line)
            idx = self.pb_splits_list.size() - 1
            self.pb_splits_list.itemconfig(idx, fg=self.pb_split_color)

    def confirm_end_run(self):
        """Finalizes the run, checks for Overall PB (Total Time), and resets the current run state."""
        if not self.current_run:
            messagebox.showinfo("Notice", "The current run is already empty.")
            return

        # Check if run is complete (all 10 stages)
        is_complete_run = len(self.current_run) >= RUN_COMPLETE_STAGES

        if not is_complete_run:
            confirm_msg = (f"This run is incomplete ({len(self.current_run)}/{RUN_COMPLETE_STAGES} stages).\n\n"
                           "Incomplete runs will NOT count toward your Personal Best.\n"
                           "Individual split times have already been saved to Dream Splits.\n"
                           "The run counter will still increment.\n\n"
                           "Do you want to end this run?")
        else:
            confirm_msg = ("Are you sure you want to end this run? "
                           "The run counter will increment, and this run's total time will be checked against the Personal Best.")

        if messagebox.askyesno("Confirm End Run", confirm_msg):
            season_data = self.get_current_season_data()
            season_data["runCount"] += 1

            # Only check for PB if the run is complete
            if is_complete_run:
                current_total_time = self.current_run[-1]["totalTimeSeconds"]
                existing_pb_time = season_data["pbTotalTimeSeconds"]
                is_new_total_pb = current_total_time < existing_pb_time

                if is_new_total_pb:
                    season_data["pbTotalTimeSeconds"] = current_total_time
                    season_data["pbRunTimes"] = [item["totalTimeSeconds"] for item in self.current_run]

                    # Show celebratory message
                    messagebox.showinfo("Overall PB Updated",
                                        f"New Overall Personal Best set {format_time(current_total_time)}")

            save_data(self.data)
            self.reset_current_run()
            self.render_all()

    def reset_current_run(self):
        self.current_run = []
        self.time_input.delete(0, tk.END)
        self.render_all()

    def confirm_wipe_all(self):
        stage = self.data["currentStage"]
        season = self.data["currentSeason"]

        if not messagebox.askyesno(
                "DANGER: Wipe All Data",
                f"Are you sure you want to wipe your Personal Bests (PB Run and Dream Splits) for {stage} Season {season}?\n\nThis cannot be undone."
        ):
            return

        choice = messagebox.askquestion(
            "Wipe Scope",
            "Do you also want to wipe Dream Run (Best Splits) data?\n\n"
            "→ Click 'Yes' to wipe EVERYTHING (PBs + Dream Runs + Run Counter)\n"
            "→ Click 'No' to wipe ONLY PB Run data and keep Dream Runs."
        )

        season_data = self.get_current_season_data()

        if choice == "yes":
            season_data["pbRunTimes"] = []
            season_data["pbTotalTimeSeconds"] = inf
            season_data["bestSplits"] = {}
            season_data["runCount"] = 0
            messagebox.showinfo("Data Wiped",
                                f"All PBs, Dream Runs, and Run Count for {stage} Season {season} have been reset.")
        else:
            season_data["pbRunTimes"] = []
            season_data["pbTotalTimeSeconds"] = inf
            season_data["runCount"] = 0
            messagebox.showinfo("Partial Wipe Complete",
                                f"PB Run and Run Count for {stage} Season {season} have been reset, Dream Splits preserved.")

        save_data(self.data)
        self.reset_current_run()
        self.render_all()

    def switch_stage(self, new_stage):
        if self.current_run:
            if not messagebox.askyesno("Current Run Active",
                                       f"You have an active run. Switching to {new_stage} will reset it. Continue?"):
                return

        self.data["currentStage"] = new_stage
        self._ensure_season_exists()
        save_data(self.data)
        self.reset_current_run()
        self.render_all()
        messagebox.showinfo("Stage Changed", f"Switched to {new_stage} Season {self.data['currentSeason']}")

    def switch_season(self, new_season):
        if self.current_run:
            if not messagebox.askyesno("Current Run Active",
                                       f"You have an active run. Switching to Season {new_season} will reset it. Continue?"):
                return

        self.data["currentSeason"] = new_season
        self._ensure_season_exists()
        save_data(self.data)
        self.reset_current_run()
        self.render_all()
        messagebox.showinfo("Season Changed", f"Switched to {self.data['currentStage']} Season {new_season}")

    def change_season_menu(self):
        stage = self.data["currentStage"]
        available_seasons = sorted([int(s) for s in self.data["seasons"][stage].keys()])

        dialog_text = f"Current: {stage} Season {self.data['currentSeason']}\n\n"
        dialog_text += f"Available seasons for {stage}: {', '.join(map(str, available_seasons))}\n\n"
        dialog_text += "Enter season number to switch to (or a new number to create):"

        result = simpledialog.askinteger("Change Season", dialog_text,
                                         initialvalue=self.data['currentSeason'],
                                         minvalue=1, maxvalue=100)

        if result is not None:
            self.switch_season(result)

    def open_config(self):
        self.data = load_data()
        config_str = json.dumps(self.data["config"], indent=4)
        messagebox.showinfo("Configuration",
                            f"To change the background/watermark, edit the **'{DATA_FILE}'** file while the app is closed.\n\nCurrent Config:\n{config_str}\n\nNote: For image paths, if the file is in the same folder as the script, just use the filename (e.g., 'image.jpg').")


if __name__ == '__main__':

    os.chdir(SCRIPT_DIR)
    root = tk.Tk()
    root.geometry("1000x600")
    try:
        root.iconbitmap('tracker_icon.ico')
    except tk.TclError:
        print("Warning: Could not load 'tracker_icon.ico' using iconbitmap.")
        if PILLOW_INSTALLED:
            try:
                icon_path = SCRIPT_DIR / 'tracker_icon.ico'
                icon_image = Image.open(icon_path)
                tk_icon = ImageTk.PhotoImage(icon_image)
                root.wm_iconphoto(True, tk_icon)
                # IMPORTANT: Keep a reference to prevent the icon from disappearing!
                root.tk_icon_ref = tk_icon
            except Exception as e:
                print(f"Warning: Could not load 'tracker_icon.ico' using Pillow/wm_iconphoto: {e}")
        else:
            print("Note: Pillow is not installed. Using only iconbitmap, which might not set the title bar icon.")
    app = SpeedRunTrackerApp(root)

    menubar = tk.Menu(root)
    root.config(menu=menubar)

    settings_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Settings", menu=settings_menu)
    settings_menu.add_command(label="View Configuration", command=app.open_config)
    stage_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Stage", menu=stage_menu)
    stage_menu.add_command(label="Switch to ECHOES", command=lambda: app.switch_stage("ECHOES"))
    stage_menu.add_command(label="Switch to ETERNITY", command=lambda: app.switch_stage("ETERNITY"))
    stage_menu.add_separator()
    stage_menu.add_command(label="Change Season...", command=app.change_season_menu)

    root.update_idletasks()
    app.load_background_image()
    app.update_widget_positions()

    root.mainloop()