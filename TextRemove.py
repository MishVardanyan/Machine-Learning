import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path
from paddleocr import PaddleOCR
import threading
from PIL import Image
import time


# Functions for handling folders and images
def add_folder():
    global selected_images, input_folder_names

    selected_folder = filedialog.askdirectory(title="Выберите папку с изображениями")
    if not selected_folder:
        return

    supported_formats = ('.jpg', '.jpeg', '.png')
    images_in_folder = [
        os.path.join(selected_folder, f) for f in os.listdir(selected_folder)
        if f.lower().endswith(supported_formats)
    ]
    if images_in_folder:
        language_selection = tk.StringVar(value="Все")
        selected_images.append((selected_folder, images_in_folder, language_selection))
        input_folder_names.append((os.path.basename(selected_folder), len(images_in_folder), language_selection))
        update_folders_list()
    else:
        messagebox.showinfo("Информация", f"В выбранной папке '{os.path.basename(selected_folder)}' нет изображений!")

def update_folders_list():
    for widget in folders_list_frame.winfo_children():
        widget.destroy()

    for idx, item in enumerate(input_folder_names, start=0):
        folder_name, image_count, language_selection = item
        frame = ttk.Frame(folders_list_frame)
        frame.pack(fill="x", pady=2, padx=10)

        folder_info = f"{idx + 1}. {folder_name} (изображений: {image_count})"
        folder_label = ttk.Label(frame, text=folder_info, anchor="w", font=("Arial", 10))
        folder_label.pack(side="left", fill="x", expand=True, padx=5)
        language_combobox = ttk.Combobox(
            frame,
            values=["Все", "Русский", "Английский", "Японский"],
            state="readonly",
            width=15
        )
        language_combobox.set(language_selection)
        language_combobox.pack(side="left", padx=5)

        language_combobox.bind(
            "<<ComboboxSelected>>",
            lambda e, idx=idx, language_combobox=language_combobox: update_language(idx, language_combobox)
        )

        delete_button = ttk.Button(frame, text="✖", width=3, command=lambda idx=idx: remove_folder(idx))
        delete_button.pack(side="right")

def update_language(idx, language_combobox):
    folder_name, image_count, _ = input_folder_names[idx]
    language_value = language_combobox.get()

    input_folder_names[idx] = (folder_name, image_count, language_value)
    selected_images[idx] = (folder_name, selected_images[idx][1], language_value)

def remove_folder(idx):
    del selected_images[idx]
    del input_folder_names[idx]
    update_folders_list()


def select_save_directory():
    global save_directory
    save_directory = filedialog.askdirectory(title="Выберите папку для сохранения")
    save_label.config(text=f"Папка: {save_directory}" if save_directory else "Папка не выбрана")


supported_formats = ('.jpg', '.jpeg', '.png')

def normalize_path(file_path):
    return os.path.normpath(str(file_path))

def process_images_thread():
    global stop_processing, pause_processing

    if not selected_images:
        messagebox.showerror("Ошибка", "Папки с изображениями не выбраны!")
        return

    if not save_directory:
        messagebox.showerror("Ошибка", "Папка для сохранения не выбрана!")
        return

    try:

        ocr_models = {
            "Русский": PaddleOCR(use_angle_cls=True, lang="cyrillic", use_gpu=False),
            "Английский": PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False),
            "Японский": PaddleOCR(use_angle_cls=True, lang="japan", use_gpu=False),
        }
        start_time = time.time()

        for folder_idx, (folder_name, images, language_selection) in enumerate(selected_images, start=1):
            selected_language = language_selection.get() if isinstance(language_selection, tk.StringVar) else language_selection


            if selected_language not in ocr_models and selected_language != "Все":
                continue

            folder_save_path = os.path.join(save_directory, Path(folder_name).name)
            os.makedirs(folder_save_path, exist_ok=True)

            for image_idx, image_path in enumerate(images, start=1):
                if stop_processing:
                    return

                while pause_processing:
                    pass

                try:
                    progress_label.config(
                        text=f"Папка {folder_idx}/{len(selected_images)}: '{Path(folder_name).name}', "
                             f"Изображение {image_idx}/{len(images)}: {Path(image_path).name}"
                    )
                    progress_label.update()

                    image_path = Path(image_path)
                    if not image_path.exists() or not image_path.suffix.lower() in supported_formats:
                        continue


                    try:
                        img = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
                        if img is None:
                            raise ValueError(f"{image_path}")
                    except Exception as e:
                        print(f"{e}")
                        continue

                    mask = np.zeros(img.shape[:2], dtype=np.uint8)


                    if selected_language == "Все":
                        languages_to_process = ocr_models.values()
                    else:
                        languages_to_process = ocr_models.values()

                    for ocr_model in languages_to_process:
                        try:
                            result = ocr_model.ocr(str(image_path), cls=False)
                            if not result or not result[0]:
                                continue

                            for line in result[0]:
                                box = np.array(line[0], dtype=np.int32)
                                cv2.fillPoly(mask, [box], 255)
                        except Exception as e:
                            print(f"OCR Ошибка՝ {e}")

                    if np.any(mask):
                        restored_image = cv2.inpaint(img, mask, inpaintRadius=30, flags=cv2.INPAINT_TELEA)
                        save_path = os.path.join(folder_save_path, f"{image_path.name}")
                        cv2.imencode('.jpg', restored_image)[1].tofile(save_path)
                    else:
                        restored_image = img
                        save_path = os.path.join(folder_save_path, f"{image_path.name}")
                        cv2.imencode('.jpg', restored_image)[1].tofile(save_path)

                except Exception as e:
                    print(f"Ошибка՝ {image_path}, {e}")

        end_time = time.time()
        duration = end_time - start_time
        messagebox.showinfo("Успех", f"Все изображения успешно обработаны!\nВремя обработки: {duration:.2f} секунд")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
    finally:
        progress_label.config(text="Процесс завершен")
        hide_controls()

def process_images():
    global stop_processing, pause_processing
    stop_processing = False
    pause_processing = False
    show_controls()
    threading.Thread(target=process_images_thread).start()


def pause_resume_process():
    global pause_processing
    pause_processing = not pause_processing
    pause_button.config(text="Продолжить" if pause_processing else "Пауза")


def stop_process():
    global stop_processing
    stop_processing = True
    progress_label.config(text="Процесс остановлен")
    hide_controls()


def show_controls():
    pause_button.pack(side="left", padx=5)
    stop_button.pack(side="left", padx=5)


def hide_controls():
    pause_button.pack_forget()
    stop_button.pack_forget()


root = tk.Tk()
root.resizable(False, False)
root.title("Удаление текста с изображений")
root.geometry("600x600")

style = ttk.Style()
style.theme_use("clam")

title_label = ttk.Label(root, text="Удаление текста с изображений", font=("Arial", 14, "bold"))
title_label.pack(pady=10)

folders_frame = ttk.Frame(root)
folders_frame.pack(fill="x", padx=20, pady=5)

add_folder_button = ttk.Button(folders_frame, text="Добавить папку", command=add_folder)
add_folder_button.pack(side="left")

folders_list_container = ttk.Frame(root)
folders_list_container.pack(fill="both", expand=True, padx=20, pady=10)

canvas = tk.Canvas(folders_list_container, height=150)
folders_list_frame = ttk.Frame(canvas)

scrollbar = ttk.Scrollbar(folders_list_container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar.set)

scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
canvas.create_window((0, 0), window=folders_list_frame, anchor="nw")

folders_list_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

save_frame = ttk.Frame(root)
save_frame.pack(fill="x", padx=20, pady=5)
save_button = ttk.Button(save_frame, text="Выбрать папку для сохранения", command=select_save_directory)
save_button.pack(side="left")
save_label = ttk.Label(save_frame, text="Папка не выбрана", anchor="w", justify="left")
save_label.pack(side="left", padx=10)

progress_label = ttk.Label(root, text="Ожидание начала процесса...", font=("Arial", 10), anchor="w")
progress_label.pack(fill="x", padx=20, pady=10)

controls_frame = ttk.Frame(root)
controls_frame.pack(fill="x", padx=20, pady=10)
process_button = ttk.Button(controls_frame, text="Начать обработку", command=process_images)
process_button.pack(side="left", padx=5)
pause_button = ttk.Button(controls_frame, text="Пауза", command=pause_resume_process)
stop_button = ttk.Button(controls_frame, text="Остановить", command=stop_process)
selected_images = []
input_folder_names = []
save_directory = ""
stop_processing = False
pause_processing = False
root.mainloop()
