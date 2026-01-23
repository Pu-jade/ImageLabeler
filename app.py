import csv
import random
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog

from PIL import Image, ImageTk, ImageOps


# Display box size (centered)
DISPLAY_W = 130
DISPLAY_H = 40

# Supported image extensions
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def sanitize_filename(name: str) -> str:
    """
    Minimal filename sanitation for Windows compatibility.
    """
    name = name.strip()
    if not name:
        return ""
    return re.sub(r'[\\/:*?"<>|]+', "_", name)


def list_images(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    return sorted(files)


def fit_center_to_box(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """
    Keep aspect ratio, fit within (box_w, box_h), then pad to exact size and center.
    """
    contained = ImageOps.contain(img, (box_w, box_h), method=Image.LANCZOS)
    canvas = Image.new("RGB", (box_w, box_h), (255, 255, 255))
    x = (box_w - contained.size[0]) // 2
    y = (box_h - contained.size[1]) // 2
    canvas.paste(contained, (x, y))
    return canvas


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Labeling Tool")
        self.geometry("640x520")
        self.resizable(False, False)

        self.user_name: str = ""
        self.csv_path: Path | None = None
        self.image_dir: Path | None = None
        self.images: list[Path] = []
        self.idx: int = 0

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (StartFrame, LabelFrame, FinishFrame):
            frame = F(parent=container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("StartFrame")

    def show_frame(self, name: str):
        self.frames[name].tkraise()

    def start_labeling(self, name_input: str, chosen_dir: str):
        name_clean = sanitize_filename(name_input)
        if not name_clean:
            messagebox.showerror("Error", "Please enter a valid name.")
            return

        if not chosen_dir.strip():
            messagebox.showerror("Error", "Please choose an image folder.")
            return

        img_dir = Path(chosen_dir).expanduser().resolve()
        imgs = list_images(img_dir)
        if not imgs:
            messagebox.showerror("Error", f"No images found in the selected folder:\n{img_dir}")
            return

        random.shuffle(imgs)

        self.user_name = name_clean
        self.image_dir = img_dir
        self.images = imgs
        self.idx = 0

        # Save CSV to the selected image folder
        self.csv_path = img_dir / f"{self.user_name}.csv"

        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["image_name", "label"])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot create CSV file:\n{self.csv_path}\n\nReason: {e}")
            return

        label_frame: LabelFrame = self.frames["LabelFrame"]
        label_frame.load_current_image()
        self.show_frame("LabelFrame")

    def save_choice_and_next(self, label_value: int):
        if self.csv_path is None:
            messagebox.showerror("Error", "CSV path not initialized.")
            return
        if not (0 <= self.idx < len(self.images)):
            return

        img_name = self.images[self.idx].name

        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([img_name, label_value])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write CSV:\n{self.csv_path}\n\nReason: {e}")
            return

        self.idx += 1
        if self.idx >= len(self.images):
            finish_frame: FinishFrame = self.frames["FinishFrame"]
            finish_frame.set_result_path(str(self.csv_path))
            self.show_frame("FinishFrame")
        else:
            label_frame: LabelFrame = self.frames["LabelFrame"]
            label_frame.load_current_image()


class StartFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Enter your name (CSV filename)", font=("Arial", 16)).pack(pady=20)

        self.name_var = tk.StringVar()
        entry = tk.Entry(self, textvariable=self.name_var, font=("Arial", 14), width=34)
        entry.pack(pady=8)
        entry.focus_set()

        tk.Label(self, text="Choose image folder", font=("Arial", 16)).pack(pady=16)

        self.dir_var = tk.StringVar(value="")
        dir_row = tk.Frame(self)
        dir_row.pack(pady=8)

        self.dir_entry = tk.Entry(dir_row, textvariable=self.dir_var, font=("Arial", 12), width=44)
        self.dir_entry.grid(row=0, column=0, padx=(0, 8))

        tk.Button(
            dir_row,
            text="Browse...",
            font=("Arial", 12),
            width=10,
            command=self.on_browse
        ).grid(row=0, column=1)

        tk.Label(
            self,
            text="Supported formats: jpg/png/webp/bmp/gif/tiff\nCSV will be saved to the selected image folder.",
            font=("Arial", 11),
            justify="center"
        ).pack(pady=16)

        tk.Button(
            self,
            text="Start",
            font=("Arial", 14),
            width=14,
            command=self.on_start
        ).pack(pady=14)

    def on_browse(self):
        folder = filedialog.askdirectory(title="Select image folder")
        if folder:
            self.dir_var.set(folder)

    def on_start(self):
        self.controller.start_labeling(self.name_var.get(), self.dir_var.get())


class LabelFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        self.progress_label = tk.Label(self, text="", font=("Arial", 14))
        self.progress_label.pack(pady=10)

        self.image_label = tk.Label(self)
        self.image_label.pack(pady=18)

        self.choice_var = tk.IntVar(value=-1)
        radio_frame = tk.Frame(self)
        radio_frame.pack(pady=10)

        tk.Radiobutton(
            radio_frame, text="positive", variable=self.choice_var, value=1, font=("Arial", 13)
        ).grid(row=0, column=0, padx=22)

        tk.Radiobutton(
            radio_frame, text="negative", variable=self.choice_var, value=0, font=("Arial", 13)
        ).grid(row=0, column=1, padx=22)

        tk.Button(
            self,
            text="Next",
            font=("Arial", 14),
            width=14,
            command=self.on_next
        ).pack(pady=16)

        self._photo_ref = None

    def load_current_image(self):
        idx = self.controller.idx
        total = len(self.controller.images)
        self.progress_label.config(text=f"{idx + 1}/{total}")
        self.choice_var.set(-1)

        img_path = self.controller.images[idx]
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{img_path}\n\nReason: {e}")
            return

        img_boxed = fit_center_to_box(img, DISPLAY_W, DISPLAY_H)
        photo = ImageTk.PhotoImage(img_boxed)
        self._photo_ref = photo
        self.image_label.config(image=photo)

    def on_next(self):
        val = self.choice_var.get()
        if val not in (0, 1):
            messagebox.showwarning("Warning", "Please select positive or negative.")
            return
        self.controller.save_choice_and_next(val)


class FinishFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="You are fantastic! 你真棒！", font=("Arial", 20)).pack(pady=90)

        self.path_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.path_var, font=("Arial", 11), justify="center").pack(pady=10)

        tk.Button(
            self,
            text="Close",
            font=("Arial", 14),
            width=14,
            command=self.controller.destroy
        ).pack(pady=24)

    def set_result_path(self, p: str):
        self.path_var.set(f"Results saved to:\n{p}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
