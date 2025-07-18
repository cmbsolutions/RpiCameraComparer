from picamera2 import Picamera2, MappedArray, Preview
from PIL import Image, ImageTk
from gpiozero import Button, OutputDevice
import tkinter as tk
import pytesseract
import threading
import time
import cv2
import sys

# ───── Configuration ─────
TRIGGER_PIN = 17
OUTPUT_PIN = 27
PULSE_TIME = 0.5  # seconds
FRAME_WIDTH = 320
FRAME_HEIGHT = 240


# ─────────────────────────

class DualOCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dual Camera OCR Monitor")
        self.roi1 = None
        self.roi2 = None
        self.rect1 = None
        self.rect2 = None
        self.drag_start = None
        self.selecting_canvas = None
        self.collecting = False
        self.ocr_lock = threading.Lock()
        self.running = True
        self.lensposition = 0.0

        # Setup two cameras
        self.cam1 = Picamera2(0)
        self.cam1.configure(self.cam1.create_preview_configuration({"size": (FRAME_WIDTH, FRAME_HEIGHT)}))
        self.cam1.start_preview()
        self.cam1.start()

        try:
            self.cam2 = Picamera2(1)
            self.cam2_available = True

        except Exception as e:
            print(f"Camera 2 not connected: {e}", file=sys.stderr)
            self.cam2 = None
            self.cam2_available = False

        #        for cam in (self.cam1, self.cam2):
        #            if cam != None:
        #                cam.preview_configuration.main.size = (FRAME_WIDTH, FRAME_HEIGHT)
        #                cam.preview_configuration.main.format = "BGR888"
        #                cam.configure("preview")
        #                cam.start()
        #                print(cam.camera_controls)

        # Setup GPIO
        self.trigger = Button(TRIGGER_PIN, pull_up=True)
        self.output = OutputDevice(OUTPUT_PIN)
        self.trigger.when_pressed = self.handle_trigger

        # UI Layout
        self.display_frame = tk.Frame(root)
        self.display_frame.pack()

        self.cam1_frame = tk.Frame(self.display_frame)
        self.cam1_frame.pack(side="left", padx=10)

        self.canvas1 = tk.Canvas(self.cam1_frame, width=FRAME_WIDTH, height=FRAME_HEIGHT)
        self.canvas1.pack()

        self.label1 = tk.Label(self.cam1_frame, text="CAM0: --", font=("Arial", 24), fg="blue")
        self.label1.pack(pady=5)

        self.cam2_frame = tk.Frame(self.display_frame)
        self.cam2_frame.pack(side="right", padx=10)

        self.canvas2 = tk.Canvas(self.cam2_frame, width=FRAME_WIDTH, height=FRAME_HEIGHT)
        self.canvas2.pack()

        self.label2 = tk.Label(self.cam2_frame, text="CAM1: --", font=("Arial", 24), fg="blue", padx=20)
        self.label2.pack(pady=5)

        self.canvas1.bind("<ButtonPress-1>", lambda e: self.on_press(e, 1))
        self.canvas1.bind("<B1-Motion>", lambda e: self.on_drag(e, 1))
        self.canvas1.bind("<ButtonRelease-1>", lambda e: self.on_release(e, 1))

        self.canvas2.bind("<ButtonPress-1>", lambda e: self.on_press(e, 2))
        self.canvas2.bind("<B1-Motion>", lambda e: self.on_drag(e, 2))
        self.canvas2.bind("<ButtonRelease-1>", lambda e: self.on_release(e, 2))

        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(fill="x")

        self.start_btn = tk.Button(self.btn_frame, text="Start Capture", state="disabled", command=self.start_capture)
        self.start_btn.pack(side="left", padx=5, pady=5)

        self.reset_btn = tk.Button(self.btn_frame, text="Reset ROIs", command=self.reset_rois)
        self.reset_btn.pack(side="left", padx=5, pady=5)

        self.test_btn = tk.Button(self.btn_frame, text="Test Capture", command=self.handle_trigger)
        self.test_btn.pack(side="left", padx=5, pady=5)

        self.focusup_btn = tk.Button(self.btn_frame, text="Focus +", command=self.focusup)
        self.focusup_btn.pack(side="left", padx=5, pady=5)
        self.focusdown_btn = tk.Button(self.btn_frame, text="Focus -", command=self.focusdown)
        self.focusdown_btn.pack(side="left", padx=5, pady=5)

        self.status_lbl = tk.Label(root, text="Draw ROI on both cameras")
        self.status_lbl.pack(fill="x")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_preview()

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(lambda: self.root.attributes('-topmost', False))

    def update_preview(self):
        if not self.running:
            return

        try:
            frame1 = self.cam1.capture_array()
            self.latest_frame1 = frame1
            img1 = ImageTk.PhotoImage(Image.fromarray(frame1))
            self.photo1 = img1
            self.canvas1.create_image(0, 0, anchor="nw", image=self.photo1)

            if self.roi1:
                x1, y1, x2, y2 = self.roi1
                self.canvas1.create_rectangle(x1, y1, x2, y2, outline="green", width=2)

            if self.cam2_available:
                frame2 = self.cam2.capture_array()
                self.latest_frame2 = frame2
                img2 = ImageTk.PhotoImage(Image.fromarray(frame2))
                self.photo2 = img2
                self.canvas2.create_image(0, 0, anchor="nw", image=self.photo2)

                if self.roi2:
                    x1, y1, x2, y2 = self.roi2
                    self.canvas2.create_rectangle(x1, y1, x2, y2, outline="green", width=2)

            if self.running:
                self.root.after(30, self.update_preview)

        except Exception as e:
            print(f"Window closed. {e}")

    def on_press(self, event, cam_id):
        if self.collecting:
            return
        self.drag_start = (event.x, event.y)
        self.selecting_canvas = cam_id
        if cam_id == 1 and self.rect1:
            self.canvas1.delete(self.rect1)
        if cam_id == 2 and self.rect2:
            self.canvas2.delete(self.rect2)

    def on_drag(self, event, cam_id):
        if not self.drag_start:
            return
        x1, y1 = self.drag_start
        x2, y2 = event.x, event.y
        if cam_id == 1:
            self.rect1 = self.canvas1.create_rectangle(x1, y1, x2, y2, outline="red")
        else:
            self.rect2 = self.canvas2.create_rectangle(x1, y1, x2, y2, outline="red")

    def on_release(self, event, cam_id):
        if not self.drag_start:
            return
        x1, y1 = self.drag_start
        x2, y2 = event.x, event.y
        roi = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if cam_id == 1:
            self.roi1 = roi
        else:
            self.roi2 = roi
        self.drag_start = None
        self.update_roi_status()

    def update_roi_status(self):
        if self.roi1 and self.roi2:
            self.start_btn.config(state="normal")
            self.status_lbl.config(text="ROIs set. Press Start to activate.")
        else:
            self.status_lbl.config(text="Draw ROI on both cameras")

    def reset_rois(self):
        self.roi1 = None
        self.roi2 = None
        if self.rect1:
            self.canvas1.delete(self.rect1)
            self.rect1 = None
        if self.rect2:
            self.canvas2.delete(self.rect2)
            self.rect2 = None
        self.start_btn.config(state="disabled")
        self.status_lbl.config(text="Draw ROI on both cameras")

    def start_capture(self):
        if self.roi1 and self.roi2:
            if self.collecting:
                self.collecting = False
                self.start_btn.config(text="Start Capture")
                self.reset_btn.config(state="active")
                self.status_lbl.config(text="Idle...")
            else:
                self.collecting = True
                self.start_btn.config(text="Stop Capture")
                self.reset_btn.config(state="disabled")
                self.status_lbl.config(text="Waiting for trigger...")

    def handle_trigger(self):
        if not self.collecting:
            return
        threading.Thread(target=self.run_dual_ocr).start()

    def focusup(self):
        self.lensposition += 0.1

        if self.lensposition > 10.0:
            self.lensposition = 10.0

        self.cam1.set_controls({"AfMode": 1, "LensPosition": self.lensposition})

    def focusdown(self):
        self.lensposition -= 0.1

        if self.lensposition < 0.0:
            self.lensposition = 0.0

        self.cam1.set_controls({"AfMode": 1, "LensPosition": self.lensposition})

    def run_dual_ocr(self):
        with self.ocr_lock:
            frame1 = self.latest_frame1

            if self.cam2_available:
                frame2 = self.latest_frame2

            def extract_digits(frame, roi):
                x1, y1, x2, y2 = roi
                cropped = frame[y1:y2, x1:x2]
                gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
                text = pytesseract.image_to_string(gray, config="--psm 7 -c tessedit_char_whitelist=0123456789")
                return ''.join(filter(str.isdigit, text))

            digits1 = extract_digits(frame1, self.roi1)
            digits2 = 0

            if self.cam2_available:
                digits2 = extract_digits(frame2, self.roi2)

            self.root.after(0, lambda: self.label1.config(text=f"CAM0: {digits1}"))
            self.root.after(0, lambda: self.label2.config(text=f"CAM1: {digits2}"))

            print(f"Camera 0 OCR: {digits1}")
            print(f"Camera 1 OCR: {digits2}")

            self.root.after(0, lambda: self.status_lbl.config(
                text=f"CAM0: {digits1} — CAM1: {digits2} — {'MATCH' if digits1 == digits2 else 'MISMATCH'}"))

            if digits1 != digits2:
                self.output.on()
                time.sleep(PULSE_TIME)
                self.output.off()

    def on_close(self):
        print("Closing app...")

        self.running = False

        try:
            self.cam1.stop()

        except Exception as e:
            print(f"Error stopping cam1: {e}")

        if self.cam2_available:
            try:
                self.cam2.stop()

            except Exception as e:
                print(f"Error stopping cam2: {e}")

        try:
            self.trigger.close()
            self.output.close()

        except Exception as e:
            print(f"GPIO cleanup error: {e}")

        self.root.quit()
        self.root.destroy()


# ─────── Main ───────
if __name__ == "__main__":
    root = tk.Tk()
    app = DualOCRApp(root)
    root.mainloop()
