import json
import os
import sys
import subprocess
import time
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
BG_COLOR = "#0b0f19"
MAX_TASKS = 5

BASE_DIR = Path(__file__).resolve().parent
TASK_FILE = BASE_DIR / "tasks.json"
WALLPAPER_FILE = BASE_DIR / "wallpaper.png"
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "walltodo.desktop"

def resolve_python_executable():
    local_venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if local_venv_python.exists():
        return local_venv_python
    return Path(sys.executable)

def load_tasks():
    if not TASK_FILE.exists():
        return {"title": "Today's Intent", "tasks": []}
    with TASK_FILE.open() as f:
        return json.load(f)

def save_tasks(data):
    with TASK_FILE.open("w") as f:
        json.dump(data, f, indent=2)

def update_wallpaper():
    data = load_tasks()
    wp = generate_wallpaper(data)
    set_wallpaper(wp)
    return wp

def generate_wallpaper(data):
    from urllib.parse import unquote, urlparse
    from PIL import ImageFilter, ImageOps

    def get_system_wallpaper():
        commands = [
            ["gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark"],
            ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
        ]

        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            uri = result.stdout.strip().strip("'")
            if uri.startswith("file://"):
                parsed = urlparse(uri)
                wallpaper_path = Path(unquote(parsed.path))
                if wallpaper_path.exists():
                    return Image.open(wallpaper_path).convert("RGBA")

        return Image.new("RGBA", (WIDTH, HEIGHT), BG_COLOR)

    def fit_text(draw, text, font_name, start_size, max_width, min_size=22):
        for size in range(start_size, min_size - 1, -2):
            font = ImageFont.truetype(font_name, size)
            bbox = draw.textbbox((0, 0), text, font=font)
            if bbox[2] - bbox[0] <= max_width:
                return font
        return ImageFont.truetype(font_name, min_size)

    def wrap_task(draw, text, font, max_width):
        words = text.split()
        if not words:
            return [""]

        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    background = ImageOps.fit(
        get_system_wallpaper(),
        (WIDTH, HEIGHT),
        method=Image.Resampling.LANCZOS,
    )
    bg_blurred = background.filter(ImageFilter.GaussianBlur(18))
    canvas = background.copy()

    panel_x = 90
    panel_y = 110
    panel_w = 760
    panel_h = 860
    panel_radius = 42

    panel_crop = bg_blurred.crop((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h))
    panel_overlay = Image.new("RGBA", (panel_w, panel_h), (18, 22, 32, 168))
    panel = Image.alpha_composite(panel_crop, panel_overlay)

    panel_draw = ImageDraw.Draw(panel)
    panel_draw.rounded_rectangle(
        (0, 0, panel_w - 1, panel_h - 1),
        radius=panel_radius,
        outline=(255, 255, 255, 42),
        width=2,
    )

    canvas.paste(panel, (panel_x, panel_y), panel)
    draw = ImageDraw.Draw(canvas)

    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
        task_font = ImageFont.truetype("DejaVuSans.ttf", 40)
        task_font_small = ImageFont.truetype("DejaVuSans.ttf", 34)
        meta_font = ImageFont.truetype("DejaVuSans.ttf", 26)
    except OSError:
        title_font = ImageFont.load_default()
        task_font = ImageFont.load_default()
        task_font_small = ImageFont.load_default()
        meta_font = ImageFont.load_default()

    title = data.get("title", "Today's Intent")
    raw_tasks = list(data.get("tasks", []))[:MAX_TASKS]
    tasks = [normalize_task(t) for t in raw_tasks]

    inner_x = panel_x + 54
    inner_right = panel_x + panel_w - 54
    current_y = panel_y + 56

    title_font = fit_text(draw, title, "DejaVuSans-Bold.ttf", 64, panel_w - 108)
    draw.text((inner_x, current_y), title, fill=(255, 255, 255, 245), font=title_font)

    title_bbox = draw.textbbox((inner_x, current_y), title, font=title_font)
    current_y = title_bbox[3] + 22

    draw.line(
        (inner_x, current_y, inner_right, current_y),
        fill=(255, 255, 255, 48),
        width=2,
    )
    current_y += 30

    task_area_width = panel_w - 108
    line_gap = 10
    block_gap = 22

    if tasks:
        for index, task_obj in enumerate(tasks):
            task_text = task_obj["text"]
            is_done = task_obj.get("done", False)
            
            fade = max(168, 238 - index * 18) if not is_done else max(100, 120 - index * 15)
            accent = max(128, 210 - index * 12) if not is_done else max(90, 110 - index * 10)
            
            bullet_color = (
                accent,
                accent + 10 if accent + 10 < 255 else 255,
                255,
                fade,
            ) if not is_done else (
                120, 140, 160, fade
            )
            
            text_color = (235 - index * 8, 240 - index * 5, 250, fade) if not is_done else (140, 160, 180, fade)
            font = task_font_small if index >= 3 else task_font
            bullet = "✓" if is_done else "•"

            lines = wrap_task(draw, task_text, font, task_area_width - 46)

            bbox = draw.textbbox((0, 0), lines[0], font=font)
            line_height = bbox[3] - bbox[1]

            draw.text((inner_x, current_y), bullet, fill=bullet_color, font=font)
            text_x = inner_x + 28

            for line_number, line in enumerate(lines):
                y_offset = current_y + line_number * (line_height + line_gap)
                draw.text((text_x, y_offset), line, fill=text_color, font=font)
                
                # Draw strikethrough for completed tasks
                if is_done:
                    line_bbox = draw.textbbox((text_x, y_offset), line, font=font)
                    strike_y = y_offset + (line_height // 2)
                    draw.line(
                        (line_bbox[0], strike_y, line_bbox[2], strike_y),
                        fill=text_color,
                        width=2,
                    )

            current_y += len(lines) * (line_height + line_gap) + block_gap - line_gap

            if current_y > panel_y + panel_h - 70:
                break
    else:
        empty_text = "Add tasks with the CLI to build your day."
        empty_font = fit_text(draw, empty_text, "DejaVuSans.ttf", 34, task_area_width)
        draw.text(
            (inner_x, current_y + 10),
            empty_text,
            fill=(230, 237, 245, 185),
            font=empty_font,
        )

    footer = "Updated from tasks.json"
    footer_bbox = draw.textbbox((0, 0), footer, font=meta_font)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_h = footer_bbox[3] - footer_bbox[1]
    footer_x = panel_x + panel_w - 54 - footer_w
    footer_y = panel_y + panel_h - 52 - footer_h
    draw.text((footer_x, footer_y), footer, fill=(255, 255, 255, 126), font=meta_font)

    path = str(WALLPAPER_FILE)
    canvas.convert("RGB").save(path)
    return path

def set_wallpaper(path):
    uri = f"file://{Path(path).resolve()}"

    commands = [
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
        ["gsettings", "set", "org.gnome.desktop.screensaver", "picture-uri", uri],
    ]

    for command in commands:
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def install_autostart():
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    python_executable = resolve_python_executable()

    entry = f"""[Desktop Entry]
Type=Application
Name=Walltodo Wallpaper
Comment=Update the Ubuntu wallpaper from walltodo on login
Exec={python_executable} {Path(__file__).resolve()}
X-GNOME-Autostart-enabled=true
NoDisplay=true
"""

    AUTOSTART_FILE.write_text(entry)
    return AUTOSTART_FILE

def normalize_task(task):
    """Convert string task to object format for backward compatibility"""
    if isinstance(task, str):
        return {"text": task, "done": False}
    return task

def add_task(task):
    data = load_tasks()
    data["tasks"].append({"text": task, "done": False})
    save_tasks(data)

def clear_tasks():
    data = load_tasks()
    data["tasks"] = []
    save_tasks(data)

def list_tasks():
    data = load_tasks()
    print(data.get("title", "Today's Intent"))
    for index, task in enumerate(data.get("tasks", []), start=1):
        task_obj = normalize_task(task)
        status = "✓" if task_obj.get("done") else "○"
        print(f"{index}. [{status}] {task_obj['text']}")
    
    # Show progress
    tasks = data.get("tasks", [])
    completed = sum(1 for t in tasks if normalize_task(t).get("done"))
    total = len(tasks)
    if total > 0:
        print(f"\nProgress: {completed}/{total} tasks completed")

def set_title(title):
    data = load_tasks()
    data["title"] = title
    save_tasks(data)

def edit_task(index, new_text):
    data = load_tasks()
    tasks = data.get("tasks", [])
    if 0 <= index < len(tasks):
        task_obj = normalize_task(tasks[index])
        task_obj["text"] = new_text
        tasks[index] = task_obj
        data["tasks"] = tasks
        save_tasks(data)
        return True
    return False

def toggle_task(index):
    """Mark a task as done/undone"""
    data = load_tasks()
    tasks = data.get("tasks", [])
    if 0 <= index < len(tasks):
        task_obj = normalize_task(tasks[index])
        task_obj["done"] = not task_obj.get("done", False)
        tasks[index] = task_obj
        data["tasks"] = tasks
        save_tasks(data)
        return task_obj["done"]
    return None

def remove_task(index):
    data = load_tasks()
    tasks = data.get("tasks", [])
    if 0 <= index < len(tasks):
        removed = tasks.pop(index)
        data["tasks"] = tasks
        save_tasks(data)
        return normalize_task(removed)["text"]
    return None

def watch_tasks(interval=1.0):
    last_mtime = None

    try:
        while True:
            try:
                current_mtime = TASK_FILE.stat().st_mtime
            except FileNotFoundError:
                current_mtime = None

            if current_mtime != last_mtime:
                update_wallpaper()
                last_mtime = current_mtime
                print("Wallpaper updated from tasks.json")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped watching tasks.json")

def build_parser():
    parser = argparse.ArgumentParser(description="Update your wallpaper from a CLI task list")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a task")
    add_parser.add_argument("task", nargs=argparse.REMAINDER, help="Task text")

    title_parser = subparsers.add_parser("title", help="Set the wallpaper title")
    title_parser.add_argument("title", nargs=argparse.REMAINDER, help="Title text")

    edit_parser = subparsers.add_parser("edit", help="Edit a task at index (0-based)")
    edit_parser.add_argument("index", type=int, help="Task index (0-based)")
    edit_parser.add_argument("task", nargs=argparse.REMAINDER, help="New task text")

    remove_parser = subparsers.add_parser("remove", help="Remove a task at index (0-based)")
    remove_parser.add_argument("index", type=int, help="Task index (0-based)")

    done_parser = subparsers.add_parser("done", help="Mark a task as done/undone at index (0-based)")
    done_parser.add_argument("index", type=int, help="Task index (0-based)")

    subparsers.add_parser("clear", help="Clear all tasks")
    subparsers.add_parser("list", help="List current tasks")
    subparsers.add_parser("render", help="Render wallpaper once")
    subparsers.add_parser("watch", help="Watch tasks.json and refresh wallpaper on changes")
    subparsers.add_parser("install", help="Install login autostart")

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        task = " ".join(args.task).strip()
        if not task:
            parser.error("add requires task text")
        add_task(task)
        update_wallpaper()
        print(f"Added task: {task}")
    elif args.command == "title":
        title = " ".join(args.title).strip()
        if not title:
            parser.error("title requires text")
        set_title(title)
        update_wallpaper()
        print(f"Updated title: {title}")
    elif args.command == "edit":
        new_text = " ".join(args.task).strip()
        if not new_text:
            parser.error("edit requires new task text")
        if edit_task(args.index, new_text):
            update_wallpaper()
            print(f"Edited task {args.index}: {new_text}")
        else:
            parser.error(f"Task index {args.index} not found")
    elif args.command == "remove":
        removed = remove_task(args.index)
        if removed is not None:
            update_wallpaper()
            print(f"Removed task {args.index}: {removed}")
        else:
            parser.error(f"Task index {args.index} not found")
    elif args.command == "done":
        result = toggle_task(args.index)
        if result is not None:
            update_wallpaper()
            status = "marked as done" if result else "marked as undone"
            print(f"Task {args.index} {status}")
        else:
            parser.error(f"Task index {args.index} not found")
    elif args.command == "clear":
        clear_tasks()
        update_wallpaper()
        print("Cleared tasks")
    elif args.command == "list":
        list_tasks()
    elif args.command == "watch":
        watch_tasks()
    elif args.command == "install":
        autostart_file = install_autostart()
        print(f"Autostart installed at {autostart_file}")
    else:
        update_wallpaper()
        print("Wallpaper updated successfully")

if __name__ == "__main__":
    main()