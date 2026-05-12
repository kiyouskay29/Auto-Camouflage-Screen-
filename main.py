import ctypes
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

from cv2 import data, GaussianBlur, Canny, CAP_PROP_FRAME_HEIGHT, cvtColor, COLOR_BGR2RGB, COLOR_BGR2GRAY, \
    CascadeClassifier, CAP_MSMF, imwrite, CAP_PROP_FRAME_WIDTH, CASCADE_SCALE_IMAGE, resize, rectangle, CAP_DSHOW, \
    VideoCapture
import threading
import time
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import datetime as dt
from pathlib import Path
import sys
import hashlib
import secrets

# ---------------- CONFIG ----------------
CAMERA_INDEX = 0
FRAME_WIDTH = 520
FRAME_HEIGHT = 390

DETECTION_INTERVAL = 0.02

# Increased Blur Strength
BLUR_KERNEL = (95, 95)        # Stronger blur
BLUR_SIGMA = 30               # Higher sigma = much smoother & stronger blur
BLUR_PASSES = 3               # Multiple blur passes for frosted glass effect

SAVE_INTRUDER_PHOTO = True
INTRUDER_DIR = Path("intruders")
INTRUDER_DIR.mkdir(exist_ok=True)

PASSWORD_FILE = Path("app_password.hash")

# Auto Restore Settings
AUTO_RESTORE_DELAY = 3.0
NO_FACE_CONFIRMATION_FRAMES = 15

def get_haar_path():
    try:
        base_path = sys._MEIPASS  # when running EXE
        return os.path.join(base_path, "haarcascade_frontalface_default.xml")
    except:
        return data.haarcascades + "haarcascade_frontalface_default.xml"

HAAR_PATH = get_haar_path()
FACE_CASCADE = CascadeClassifier(HAAR_PATH)

if FACE_CASCADE.empty():
    print("ERROR: Could not load Haar cascade classifier!")
    sys.exit(1)

# ---------------- PASSWORD HELPERS ----------------
def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = secrets.token_bytes(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt + pwd_hash


def verify_password(stored_bytes: bytes, provided_password: str):
    salt = stored_bytes[:16]
    stored_hash = stored_bytes[16:]
    provided_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return provided_hash == stored_hash


def load_password_hash():
    if PASSWORD_FILE.exists():
        with open(PASSWORD_FILE, "rb") as f:
            return f.read()
    return None


def save_password_hash(hashed_bytes: bytes):
    with open(PASSWORD_FILE, "wb") as f:
        f.write(hashed_bytes)


# ---------------- MAIN APPLICATION ----------------
class AutoCamouflageApp:
    def __init__(self, master):
        self.master = master
        self.master.title("⚡ Auto Camouflage • PRIVACY PROTOCOL")
        self.master.configure(bg="#0a0a0f")
        self.master.geometry("1000x950")   # Start maximized
        self.master.withdraw()

        self.armed = False
        self.running = False
        self.last_detect_time = 0
        self.overlay = None
        self.cap = None
        self.current_imgtk = None
        self.max_allowed_faces = tk.IntVar(value=1)

        self.no_intruder_counter = 0
        self.last_intruder_time = 0

        self.stored_hash = load_password_hash()
        self._lock = threading.Lock()

        self.show_password_screen()

    # ====================== LOGIN ======================
    def show_password_screen(self):
        self.login_window = tk.Toplevel(self.master)
        self.login_window.title("Auto Camouflage • ACCESS")
        self.login_window.geometry("480x380")
        self.login_window.configure(bg="#0a0a0f")
        self.login_window.resizable(False, False)
        self.login_window.protocol("WM_DELETE_WINDOW", self.quit_app)

        tk.Label(self.login_window, text="⚡ Auto Camouflage",
                 font=("Segoe UI", 24, "bold"), fg="#00f5ff", bg="#0a0a0f").pack(pady=(50, 5))
        tk.Label(self.login_window, text="PRIVACY PROTOCOL v2.7",
                 font=("Segoe UI", 10), fg="#ff00aa", bg="#0a0a0f").pack(pady=(0, 30))

        tk.Label(self.login_window, text="ENTER ACCESS CODE",
                 fg="#bbbbbb", bg="#0a0a0f", font=("Segoe UI", 11)).pack(pady=8)

        self.pass_var = tk.StringVar()
        self.show_pass = tk.BooleanVar(value=False)

        entry_frame = tk.Frame(self.login_window, bg="#0a0a0f")
        entry_frame.pack(pady=15)

        self.pass_entry = ttk.Entry(entry_frame, textvariable=self.pass_var, width=32,
                                    font=("Consolas", 13), show="•")
        self.pass_entry.pack(side="left", padx=10)
        self.pass_entry.focus()

        ttk.Checkbutton(entry_frame, text="SHOW", variable=self.show_pass,
                        command=self.toggle_password_visibility, style="Neon.TCheckbutton").pack(side="left")

        btn_frame = tk.Frame(self.login_window, bg="#0a0a0f")
        btn_frame.pack(pady=40)

        ttk.Button(btn_frame, text="UNLOCK", command=self.check_password, style="Neon.TButton").pack(side="left", padx=15)
        ttk.Button(btn_frame, text="EXIT GRID", command=self.quit_app, style="Danger.TButton").pack(side="left", padx=15)

        self.pass_entry.bind("<Return>", lambda e: self.check_password())

        if not self.stored_hash:
            tk.Label(self.login_window, text="FIRST BOOT → SET YOUR NEON KEY (6+ chars)",
                     fg="#39ff14", bg="#0a0a0f", font=("Segoe UI", 10)).pack(pady=25)

    def toggle_password_visibility(self):
        self.pass_entry.config(show="" if self.show_pass.get() else "•")

    def check_password(self):
        password = self.pass_var.get().strip()
        if not password:
            messagebox.showwarning("NULL INPUT", "ENTER ACCESS CODE")
            return

        if not self.stored_hash:
            if len(password) < 6:
                messagebox.showerror("WEAK SIGNAL", "KEY MUST BE 6+ CHARACTERS")
                return
            save_password_hash(hash_password(password))
            self.stored_hash = load_password_hash()
            messagebox.showinfo("KEY ESTABLISHED", "Auto Camouflage ACTIVATED")
        else:
            if not verify_password(self.stored_hash, password):
                messagebox.showerror("ACCESS DENIED", "INVALID NEON KEY")
                self.pass_var.set("")
                self.pass_entry.focus()
                return

        self.login_window.destroy()
        self.master.deiconify()
        self._build_neon_ui()

    # ====================== NEON UI ======================
    def _build_neon_ui(self):
        main_frame = tk.Frame(self.master, bg="#0a0a0f")
        main_frame.pack(fill="both", expand=True)

        header = tk.Frame(main_frame, bg="#0a0a0f")
        header.pack(fill="x", pady=(0, 20))
        tk.Label(header, text="⚡ Auto Camouflage", font=("Segoe UI", 28, "bold"),
                 fg="#00f5ff", bg="#0a0a0f").pack(side="left")
        tk.Label(header, text="PRIVACY PROTOCOL", font=("Segoe UI", 12),
                 fg="#ff00aa", bg="#0a0a0f").pack(side="left", padx=20, pady=10)

        # Settings
        setting_frame = tk.LabelFrame(main_frame, text=" FACE THRESHOLD ",
                                      bg="#12121a", fg="#00f5ff", font=("Segoe UI", 11, "bold"))
        setting_frame.pack(fill="x", pady=10, padx=10)

        inner = tk.Frame(setting_frame, bg="#12121a")
        inner.pack(padx=20, pady=15, fill="x")

        tk.Label(inner, text="MAX ALLOWED FACES:", bg="#12121a", fg="#cccccc",
                 font=("Segoe UI", 11)).pack(side="left")

        self.face_slider = ttk.Scale(inner, from_=1, to=8, orient="horizontal",
                                     variable=self.max_allowed_faces, length=260,
                                     command=self._on_faces_limit_changed)
        self.face_slider.pack(side="left", padx=15)

        self.face_entry = ttk.Entry(inner, textvariable=self.max_allowed_faces,
                                    width=6, font=("Consolas", 12), justify="center")
        self.face_entry.pack(side="left", padx=8)
        self.face_entry.bind("<Return>", self._on_faces_limit_changed)
        self.face_entry.bind("<FocusOut>", self._on_faces_limit_changed)

        self.limit_label = tk.Label(inner, text=" LIMIT: 1 ", bg="#1f1f2e", fg="#39ff14",
                                    font=("Consolas", 11, "bold"), padx=12, pady=4)
        self.limit_label.pack(side="left", padx=15)
        self._update_limit_label()

        # Info Row
        info_frame = tk.Frame(main_frame, bg="#0a0a0f")
        info_frame.pack(pady=10, fill="x")

        self.mode_var = tk.StringVar(value="MODE: DISARMED")
        self.faces_var = tk.StringVar(value="FACES: 0")
        self.intruder_var = tk.StringVar(value="STATUS: SAFE")

        tk.Label(info_frame, textvariable=self.mode_var, fg="#ff00aa", bg="#12121a",
                 font=("Segoe UI", 13, "bold"), padx=20, pady=10, relief="solid", bd=1).grid(row=0, column=0, padx=10, sticky="ew")
        tk.Label(info_frame, textvariable=self.faces_var, fg="#00f5ff", bg="#12121a",
                 font=("Consolas", 12), padx=20, pady=10, relief="solid", bd=1).grid(row=0, column=1, padx=10, sticky="ew")
        self.intruder_label = tk.Label(info_frame, textvariable=self.intruder_var, fg="#39ff14",
                                       bg="#12121a", font=("Segoe UI", 12, "bold"), padx=20, pady=10, relief="solid", bd=1)
        self.intruder_label.grid(row=0, column=2, padx=10, sticky="ew")

        # Video Feed
        video_frame = tk.Frame(main_frame, bg="#00f5ff", padx=4, pady=4)
        video_frame.pack(pady=15)
        self.video_label = tk.Label(video_frame, bg="#000000")
        self.video_label.pack()

        self.status_var = tk.StringVar(value="SYSTEM DISARMED")
        self.status_label = tk.Label(main_frame, textvariable=self.status_var,
                                     fg="#ff00aa", bg="#0a0a0f", font=("Segoe UI", 15, "bold"))
        self.status_label.pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg="#0a0a0f")
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="▶ START CAM", command=self.start_camera, style="Neon.TButton").grid(row=0, column=0, padx=8)
        ttk.Button(btn_frame, text="🔒 ARM SYSTEM", command=self.toggle_arm, style="Neon.TButton").grid(row=0, column=1, padx=8)
        ttk.Button(btn_frame, text="⛔ STOP CAM", command=self.stop_camera, style="Danger.TButton").grid(row=0, column=2, padx=8)
        ttk.Button(btn_frame, text="📁 INTRUDERS", command=self.open_intruder_folder, style="Neon.TButton").grid(row=0, column=3, padx=8)
        ttk.Button(btn_frame, text="🔑 CHANGE KEY", command=self.show_change_password_dialog, style="Accent.TButton").grid(row=0, column=4, padx=8)
        ttk.Button(btn_frame, text="EXIT GRID", command=self.quit_app, style="Danger.TButton").grid(row=0, column=5, padx=8)

        hint = tk.Label(main_frame, text="⚠️ SCREEN BLUR DETECTED → PRESS ESC OR 1 TO RESTORE",
                        bg="#0a0a0f", fg="#ff00aa", font=("Consolas", 10))
        hint.pack(side="bottom", pady=20)

        self._apply_neon_styles()

        self.master.bind("<Escape>", self.clear_overlay)
        self.master.bind("1", self.clear_overlay)
        self.master.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _apply_neon_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Neon.TButton", font=("Segoe UI", 10, "bold"), padding=10, background="#1f1f2e", foreground="#00f5ff")
        style.map("Neon.TButton", background=[("active", "#00f5ff")], foreground=[("active", "#0a0a0f")])
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=10, background="#ff00aa", foreground="#ffffff")
        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), padding=10, background="#ff0044", foreground="#ffffff")
        style.configure("Neon.TCheckbutton", font=("Segoe UI", 10), foreground="#00f5ff", background="#0a0a0f")

    # ====================== CAMERA ======================
    def start_camera(self):
        if self.running:
            return

        self.status_var.set("TRYING TO CONNECT CAMERA...")
        self.status_label.config(fg="#f0ad4e")

        backends = [CAP_DSHOW, CAP_MSMF, 0]
        indices = [0, 1, -1, 2]

        success = False
        for backend in backends:
            for idx in indices:
                try:
                    self.cap = VideoCapture(idx, backend)
                    if self.cap.isOpened():
                        self.cap.set(CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                        self.cap.set(CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                        print(f"Camera opened - Index: {idx}")
                        success = True
                        break
                except:
                    if self.cap:
                        self.cap.release()
            if success:
                break

        if success:
            self.running = True
            self.status_var.set("CAMERA ONLINE")
            self.status_label.config(fg="#39ff14")
            threading.Thread(target=self.video_loop, daemon=True).start()
        else:
            self.status_var.set("CAMERA FAILED")
            self.status_label.config(fg="#ff0044")
            messagebox.showerror("Camera Error", "Could not open camera.\nRun PyCharm as Administrator.")

    def stop_camera(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.status_var.set("CAMERA OFFLINE")
        self.status_label.config(fg="#ff0044")

    def toggle_arm(self):
        self.armed = not self.armed
        if self.armed:
            self.mode_var.set("MODE: ARMED")
            self.status_var.set("SHIELD ACTIVE")
            self.status_label.config(fg="#39ff14")
        else:
            self.mode_var.set("MODE: DISARMED")
            self.status_var.set("SHIELD DOWN")
            self.status_label.config(fg="#ff00aa")

    def open_intruder_folder(self):
        try:
            os.startfile(str(INTRUDER_DIR))
        except:
            pass

    # ====================== STRONGER BLUR FUNCTION ======================
    def grab_blurred_screenshot(self):
        """Stronger multi-pass blur for better privacy"""
        try:
            img = pyautogui.screenshot()
            img = img.convert("RGB")
            arr = np.array(img)[:, :, ::-1]   # RGB to BGR

            # Apply strong blur multiple times
            for _ in range(BLUR_PASSES):
                arr = GaussianBlur(arr, BLUR_KERNEL, BLUR_SIGMA)

            arr = cvtColor(arr, COLOR_BGR2RGB)
            return Image.fromarray(arr)
        except Exception:
            return Image.new("RGB", (1920, 1080), color="black")

    # ====================== CAMOUFLAGE & AUTO RESTORE ======================
    def trigger_camouflage(self, frame):
        if self.overlay and self.overlay.winfo_exists():
            return

        save_intruder(frame, reason="faces")
        self.armed = False
        self.status_var.set("INTRUSION DETECTED - SCREEN BLURRED")
        self.status_label.config(fg="#ff0044")
        self.intruder_var.set("INTRUDER ALERT!")
        self.intruder_label.config(fg="#ff00aa")

        self.overlay = tk.Toplevel(self.master)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.configure(bg="black")
        self.overlay.overrideredirect(True)

        try:
            blurred = self.grab_blurred_screenshot()   # Use stronger blur
            tk_img = ImageTk.PhotoImage(blurred)
            lbl = tk.Label(self.overlay, image=tk_img, bg="black")
            lbl.image = tk_img
            lbl.pack(fill="both", expand=True)
        except:
            pass

        self.overlay.bind("<Escape>", self.clear_overlay)
        self.overlay.bind("1", self.clear_overlay)

        self.no_intruder_counter = 0
        self.last_intruder_time = time.time()

    def clear_overlay(self, event=None):
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
            self.overlay = None

        self.armed = True
        self.last_detect_time = time.time()
        self.status_var.set("SHIELD RESTORED")
        self.status_label.config(fg="#39ff14")
        self.mode_var.set("MODE: ARMED")
        self.intruder_var.set("STATUS: SAFE")
        self.intruder_label.config(fg="#39ff14")
        self.no_intruder_counter = 0

    def _update_limit_label(self):
        self.limit_label.config(text=f" LIMIT: {self.max_allowed_faces.get()} ")

    def _on_faces_limit_changed(self, event=None):
        try:
            value = int(self.max_allowed_faces.get())
            value = max(1, min(8, value))
            self.max_allowed_faces.set(value)
        except:
            self.max_allowed_faces.set(1)
        self._update_limit_label()

    def show_change_password_dialog(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("🔑 REPROGRAM NEON KEY")
        dialog.geometry("460x440")
        dialog.configure(bg="#0a0a0f")
        dialog.resizable(False, False)
        dialog.transient(self.master)
        dialog.grab_set()

        tk.Label(dialog, text="REPROGRAM ACCESS KEY", font=("Segoe UI", 16, "bold"),
                 fg="#00f5ff", bg="#0a0a0f").pack(pady=30)

        self.current_var = tk.StringVar()
        self.new_var = tk.StringVar()
        self.confirm_var = tk.StringVar()

        for text, var in [("CURRENT KEY", self.current_var), ("NEW KEY", self.new_var), ("CONFIRM KEY", self.confirm_var)]:
            tk.Label(dialog, text=text, fg="#bbbbbb", bg="#0a0a0f", font=("Segoe UI", 10)).pack(anchor="w", padx=60, pady=(15, 3))
            ttk.Entry(dialog, textvariable=var, width=34, show="•", font=("Consolas", 11)).pack(pady=5, padx=60)

        def change_password():
            current = self.current_var.get().strip()
            new_pwd = self.new_var.get().strip()
            confirm = self.confirm_var.get().strip()

            if not all([current, new_pwd, confirm]):
                messagebox.showwarning("NULL FIELD", "ALL FIELDS REQUIRED", parent=dialog)
                return
            if not verify_password(self.stored_hash, current):
                messagebox.showerror("INVALID", "CURRENT KEY MISMATCH", parent=dialog)
                return
            if len(new_pwd) < 6:
                messagebox.showerror("WEAK", "NEW KEY MUST BE 6+ CHARS", parent=dialog)
                return
            if new_pwd != confirm:
                messagebox.showerror("MISMATCH", "KEYS DO NOT MATCH", parent=dialog)
                return

            save_password_hash(hash_password(new_pwd))
            self.stored_hash = load_password_hash()
            messagebox.showinfo("SUCCESS", "NEON KEY UPDATED", parent=dialog)
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg="#0a0a0f")
        btn_frame.pack(pady=30)
        ttk.Button(btn_frame, text="REPROGRAM", command=change_password, style="Accent.TButton").pack(side="left", padx=12)
        ttk.Button(btn_frame, text="CANCEL", command=dialog.destroy, style="Danger.TButton").pack(side="left", padx=12)

    # ====================== VIDEO LOOP ======================
    def video_loop(self):
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            small_frame = resize(frame, (0, 0), fx=0.5, fy=0.5)
            gray = cvtColor(small_frame, COLOR_BGR2GRAY)
            faces_small = FACE_CASCADE.detectMultiScale(
                gray,
                scaleFactor=1.2,  # less false positives
                minNeighbors=8,  # stricter face confirmation
                minSize=(80, 80),  # ignore tiny fake detections
                flags=CASCADE_SCALE_IMAGE
            )
            valid_faces = []

            for (x, y, w, h) in faces_small:

                # Face should be roughly square
                aspect_ratio = w / float(h)
                if aspect_ratio < 0.8 or aspect_ratio > 1.3:
                    continue

                # Reject too small detections
                if w < 80 or h < 80:
                    continue

                # Face region should contain enough detail
                roi = gray[y:y + h, x:x + w]

                if roi.size == 0:
                    continue

                edges = Canny(roi, 50, 150)

                # Fake detections (shirt folds, arm edges) usually low-quality
                if np.mean(edges) < 15:
                    continue

                valid_faces.append((x, y, w, h))

            faces_small = valid_faces
            h, w = frame.shape[:2]
            sx, sy = w / small_frame.shape[1], h / small_frame.shape[0]
            faces = [(int(x*sx), int(y*sy), int(fw*sx), int(fh*sy)) for (x, y, fw, fh) in faces_small]

            for (x, y, fw, fh) in faces:
                rectangle(frame, (x, y), (x + fw, y + fh), (0, 255, 100), 2)

            current_limit = self.max_allowed_faces.get()
            intruder_detected = len(faces) > current_limit

            with self._lock:
                self.faces_var.set(f"FACES: {len(faces)}")
                if intruder_detected:
                    self.intruder_var.set(f"ALERT >{current_limit}")
                    self.intruder_label.config(fg="#ff00aa")
                else:
                    self.intruder_var.set("STATUS: SAFE")
                    self.intruder_label.config(fg="#39ff14")

            now = time.time()

            if self.armed and intruder_detected and (now - self.last_detect_time) > DETECTION_INTERVAL:
                self.last_detect_time = now
                self.master.after(0, self.trigger_camouflage, frame.copy())

            # Auto Restore
            if self.overlay and self.overlay.winfo_exists():
                if not intruder_detected:
                    self.no_intruder_counter += 1
                else:
                    self.no_intruder_counter = 0
                    self.last_intruder_time = now

                if self.no_intruder_counter >= NO_FACE_CONFIRMATION_FRAMES:
                    if (now - self.last_intruder_time) >= AUTO_RESTORE_DELAY:
                        print("Auto-restoring screen - intruder gone")
                        self.master.after(0, self.clear_overlay)

            try:
                frame_rgb = cvtColor(frame, COLOR_BGR2RGB)
                imgtk = ImageTk.PhotoImage(Image.fromarray(frame_rgb))
                self.master.after(0, self._update_video_label, imgtk)
            except:
                pass

            time.sleep(0.03)

        if self.cap:
            self.cap.release()

    def _update_video_label(self, imgtk):
        self.current_imgtk = imgtk
        self.video_label.configure(image=imgtk)

    def quit_app(self):
        self.running = False
        if self.cap:
            self.cap.release()
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.master.destroy()


# ---------------- HELPERS ----------------
def save_intruder(frame_bgr, reason="unknown"):
    if not SAVE_INTRUDER_PHOTO:
        return
    try:
        ts = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = INTRUDER_DIR / f"intruder_{reason}_{ts}.jpg"
        imwrite(str(filename), frame_bgr)
    except Exception as e:
        print(f"Save failed: {e}")


if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    app = AutoCamouflageApp(root)
    root.mainloop()
