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
ACCENT_COLOR = "#7c3aed"  # Purple accent for bullets, dividers

BASE_DIR = Path(__file__).resolve().parent
TASK_FILE = BASE_DIR / "tasks.json"
WALLPAPER_FILE = BASE_DIR / "wallpaper.png"
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "walltodo.desktop"
CONFIG_FILE = BASE_DIR / "config.json"

def resolve_python_executable():
    local_venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if local_venv_python.exists():
        return local_venv_python
    return Path(sys.executable)

def get_current_system_wallpaper_path():
    """Return current GNOME wallpaper path when available and not walltodo output."""
    from urllib.parse import unquote, urlparse

    commands = [
        ["gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark"],
        ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
    ]

    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            uri = result.stdout.strip().strip("'")
            if not uri.startswith("file://"):
                continue
            parsed = urlparse(uri)
            wallpaper_path = Path(unquote(parsed.path)).resolve()
            if wallpaper_path.exists() and wallpaper_path != WALLPAPER_FILE.resolve():
                return str(wallpaper_path)
        except Exception:
            continue
    return None

def get_wallpaper_source_state():
    """Return (path, mtime) for current non-walltodo wallpaper source."""
    path = get_current_system_wallpaper_path()
    if not path:
        return None, None
    try:
        return path, Path(path).stat().st_mtime
    except OSError:
        return path, None

# ============================================================================
# Data Model & Configuration
# ============================================================================

def load_config():
    """Load or create default layout/accent configuration"""
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open() as f:
            return json.load(f)
    return {
        "layout": "left",  # left, right, minimal
        "accent_color": ACCENT_COLOR,
    }

def save_config(config):
    """Save layout/accent configuration"""
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)

def ensure_task_object(task):
    """Convert string task to full object format"""
    if isinstance(task, str):
        return {"text": task, "done": False, "count": 1}
    if "count" not in task:
        task["count"] = 1
    return task

# ============================================================================
# Smart Prioritization (AI-lite)
# ============================================================================

def prioritize_tasks(tasks):
    """
    Reorder tasks by priority heuristic:
    - Unfinished tasks first (sorted by frequency + alphabetically)
    - Completed tasks at bottom (sorted by frequency)
    
    Priority score = (not done) * 1000 + frequency_score
    """
    if not tasks:
        return []
    
    # Normalize all tasks to object format
    normalized = [ensure_task_object(t) for t in tasks]
    
    def priority_score(task):
        is_done = task.get("done", False)
        count = task.get("count", 1)
        # Unfinished tasks get 1000x boost, then sort by frequency
        done_score = 1000 if not is_done else 0
        frequency_score = count
        text_score = ord(task["text"][0].lower()) if task["text"] else 0
        return (done_score + frequency_score, -text_score)
    
    return sorted(normalized, key=priority_score, reverse=True)

# ============================================================================
# Streak System
# ============================================================================

def get_today():
    """Get today's date in YYYY-MM-DD format"""
    from datetime import date
    return date.today().isoformat()

def update_streak(data):
    """
    Update streak tracking:
    - If task completed today, increment streak
    - If gap > 1 day, reset streak
    Returns updated data
    """
    from datetime import date, timedelta
    
    today = get_today()
    last_date = data.get("last_completed_date")
    streak = data.get("streak", 0)
    
    # Check if any task was completed today
    tasks = data.get("tasks", [])
    has_completed_today = any(ensure_task_object(t).get("done") for t in tasks)
    
    if has_completed_today:
        if last_date is None:
            streak = 1
        else:
            last = date.fromisoformat(last_date)
            today_date = date.fromisoformat(today)
            diff = (today_date - last).days
            
            if diff == 0:
                # Already updated today, don't double-count
                pass
            elif diff == 1:
                # Consecutive day, increment streak
                streak += 1
            else:
                # Gap detected, reset streak
                streak = 1
        
        data["streak"] = streak
        data["last_completed_date"] = today
    
    return data

# ============================================================================
# Visual Enhancements
# ============================================================================

def get_time_aware_colors():
    """
    Return color scheme based on time of day:
    Morning (6-18): bright colors
    Night (18-6): dimmer + warmer tone
    """
    from datetime import datetime
    hour = datetime.now().hour
    
    if 6 <= hour < 18:
        # Morning/day: bright
        return {
            "text": (235, 240, 250),
            "accent": (124, 58, 237),  # Vibrant purple
            "divider": (255, 255, 255),
        }
    else:
        # Night: dimmer + warmer
        return {
            "text": (200, 210, 220),
            "accent": (200, 140, 100),  # Warm orange/rust
            "divider": (220, 200, 180),
        }

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def add_drop_shadow(image, offset=(8, 8), blur=15, opacity=0.3):
    """
    Add drop shadow to an image.
    Returns image with shadow composited.
    """
    from PIL import ImageFilter
    
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_mask = Image.new("L", image.size, 0)
    
    # Create shadow by blurring a dark offset copy
    dark_layer = Image.new("RGBA", image.size, (0, 0, 0, int(255 * opacity)))
    dark_layer.paste((0, 0, 0, 0), (0, 0), image.split()[3] if len(image.split()) > 3 else None)
    
    shadow_blurred = dark_layer.filter(ImageFilter.GaussianBlur(blur))
    shadow_offset = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_offset.paste(shadow_blurred, offset, shadow_blurred)
    
    result = Image.alpha_composite(shadow_offset, image)
    return result

def add_gradient_overlay(image, color_top, color_bottom, opacity=0.15):
    """
    Add vertical gradient overlay from top (color_top) to bottom (transparent).
    """
    gradient = Image.new("RGBA", image.size)
    gradient_draw = ImageDraw.Draw(gradient)
    
    for y in range(image.size[1]):
        ratio = y / image.size[1]
        alpha = int(255 * opacity * (1 - ratio))  # Fade out towards bottom
        
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        
        gradient_draw.line([(0, y), (image.size[0], y)], fill=(r, g, b, alpha))
    
    return Image.alpha_composite(image, gradient)

def load_tasks():
    if not TASK_FILE.exists():
        return {"title": "Today's Intent", "tasks": [], "streak": 0, "last_completed_date": None}
    with TASK_FILE.open() as f:
        data = json.load(f)
        # Ensure streak fields exist for backward compatibility
        if "streak" not in data:
            data["streak"] = 0
        if "last_completed_date" not in data:
            data["last_completed_date"] = None
        return data

def save_tasks(data):
    with TASK_FILE.open("w") as f:
        json.dump(data, f, indent=2)

def update_wallpaper(focus_index=None, layout=None):
    try:
        config = load_config()
        current_bg = get_current_system_wallpaper_path()
        if current_bg and config.get("base_wallpaper") != current_bg:
            config["base_wallpaper"] = current_bg
            save_config(config)

        data = load_tasks()
        # Update streak when rendering, but persist only if data changed.
        before = json.dumps(data, sort_keys=True)
        data = update_streak(data)
        after = json.dumps(data, sort_keys=True)
        if before != after:
            save_tasks(data)
        wp = generate_wallpaper(data, focus_task_index=focus_index, layout=layout)
        set_wallpaper(wp)
        return wp
    except Exception as e:
        print(f"Error updating wallpaper: {e}", file=sys.stderr)
        return None

def generate_wallpaper(data, focus_task_index=None, layout=None):
    """
    Generate wallpaper from task data with optional focus mode and layout.
    
    Args:
        data: Task data dict with title, tasks, streak, etc.
        focus_task_index: If set, show only this task in focus mode (int or None)
        layout: Layout mode ("left", "right", "minimal") or None to use config
    """
    from urllib.parse import unquote, urlparse
    from PIL import ImageFilter, ImageOps

    config = load_config()
    # Load layout if not provided
    if layout is None:
        layout = config.get("layout", "left")

    def get_system_wallpaper():
        commands = [
            ["gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark"],
            ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
        ]

        saved_base = config.get("base_wallpaper") if isinstance(config, dict) else None

        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            uri = result.stdout.strip().strip("'")
            if uri.startswith("file://"):
                parsed = urlparse(uri)
                wallpaper_path = Path(unquote(parsed.path))
                # Avoid reading our own generated wallpaper as source background.
                if wallpaper_path.resolve() == WALLPAPER_FILE.resolve():
                    continue
                if wallpaper_path.exists():
                    if config.get("base_wallpaper") != str(wallpaper_path):
                        config["base_wallpaper"] = str(wallpaper_path)
                        save_config(config)
                    try:
                        return Image.open(wallpaper_path).convert("RGBA")
                    except (OSError, IOError):
                        # File is corrupted or being written, skip to next
                        continue

        if saved_base:
            saved_path = Path(saved_base)
            if saved_path.exists() and saved_path.resolve() != WALLPAPER_FILE.resolve():
                try:
                    return Image.open(saved_path).convert("RGBA")
                except (OSError, IOError):
                    pass

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

    # Load background
    background = ImageOps.fit(
        get_system_wallpaper(),
        (WIDTH, HEIGHT),
        method=Image.Resampling.LANCZOS,
    )
    bg_blurred = background.filter(ImageFilter.GaussianBlur(18))
    canvas = background.copy()
    draw = ImageDraw.Draw(canvas)

    # Get time-aware colors
    time_colors = get_time_aware_colors()
    accent_rgb = tuple(time_colors["accent"])

    # Load fonts
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
        task_font = ImageFont.truetype("DejaVuSans.ttf", 40)
        task_font_small = ImageFont.truetype("DejaVuSans.ttf", 34)
        meta_font = ImageFont.truetype("DejaVuSans.ttf", 26)
        focus_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 96)
    except OSError:
        title_font = task_font = task_font_small = meta_font = focus_font = ImageFont.load_default()

    # ===== FOCUS MODE =====
    if focus_task_index is not None:
        raw_tasks = data.get("tasks", [])
        if 0 <= focus_task_index < len(raw_tasks):
            task_obj = normalize_task(raw_tasks[focus_task_index])
            task_text = task_obj["text"]
            
            # Create centered panel for focus mode
            focus_panel_w = 1200
            focus_panel_h = 400
            focus_panel_x = (WIDTH - focus_panel_w) // 2
            focus_panel_y = (HEIGHT - focus_panel_h) // 2
            
            # Panel background
            panel_crop = bg_blurred.crop((focus_panel_x, focus_panel_y, 
                                         focus_panel_x + focus_panel_w, 
                                         focus_panel_y + focus_panel_h))
            panel_overlay = Image.new("RGBA", (focus_panel_w, focus_panel_h), (18, 22, 32, 200))
            panel = Image.alpha_composite(panel_crop, panel_overlay)
            
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (0, 0, focus_panel_w - 1, focus_panel_h - 1),
                radius=30,
                outline=accent_rgb + (180,),
                width=3,
            )
            
            canvas.paste(panel, (focus_panel_x, focus_panel_y), panel)
            
            # Centered task text
            font = fit_text(draw, task_text, "DejaVuSans-Bold.ttf", 88, 
                          focus_panel_w - 120, min_size=48)
            lines = wrap_task(draw, task_text, font, focus_panel_w - 120)
            
            text_y = focus_panel_y + (focus_panel_h - len(lines) * 100) // 2
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_w = bbox[2] - bbox[0]
                text_x = focus_panel_x + (focus_panel_w - line_w) // 2
                draw.text((text_x, text_y), line, fill=tuple(time_colors["text"]) + (245,), 
                         font=font)
                text_y += 100
            
            # Add subtle footer
            path = str(WALLPAPER_FILE)
            canvas.convert("RGB").save(path)
            return path

    # ===== STANDARD MODE WITH LAYOUT =====
    # Determine panel position and size based on layout
    # Initialize with defaults
    panel_x = 90
    panel_y = 110
    panel_w = 760
    panel_h = 860
    panel_radius = 42
    
    # Override based on layout selection
    if layout == "right":
        panel_x = WIDTH - 850
        panel_y = 110
        panel_w = 760
        panel_h = 860
    elif layout == "minimal":
        panel_x = (WIDTH - 600) // 2
        panel_y = (HEIGHT - 400) // 2
        panel_w = 600
        panel_h = 400
    # else: left (default) - already set above

    # Build panel with gradient and shadow effect
    panel_crop = bg_blurred.crop((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h))
    panel_overlay = Image.new("RGBA", (panel_w, panel_h), (18, 22, 32, 168))
    panel = Image.alpha_composite(panel_crop, panel_overlay)
    
    # Add subtle gradient overlay
    panel = add_gradient_overlay(panel, accent_rgb, (18, 22, 32), opacity=0.08)

    panel_draw = ImageDraw.Draw(panel)
    panel_draw.rounded_rectangle(
        (0, 0, panel_w - 1, panel_h - 1),
        radius=panel_radius,
        outline=accent_rgb + (100,),  # Use accent color for border
        width=2,
    )

    canvas.paste(panel, (panel_x, panel_y), panel)
    draw = ImageDraw.Draw(canvas)

    title = data.get("title", "Today's Intent")
    raw_tasks = list(data.get("tasks", []))
    
    # Apply smart prioritization
    tasks = prioritize_tasks(raw_tasks)
    
    # Limit tasks based on layout
    if layout == "minimal":
        tasks = tasks[:2]
    else:
        tasks = tasks[:MAX_TASKS]

    inner_x = panel_x + 54
    inner_right = panel_x + panel_w - 54
    current_y = panel_y + 56

    # Title
    title_font = fit_text(draw, title, "DejaVuSans-Bold.ttf", 64, panel_w - 108)
    draw.text((inner_x, current_y), title, fill=tuple(time_colors["text"]) + (245,), 
             font=title_font)

    title_bbox = draw.textbbox((inner_x, current_y), title, font=title_font)
    current_y = title_bbox[3] + 22

    # Divider with accent color
    draw.line(
        (inner_x, current_y, inner_right, current_y),
        fill=accent_rgb + (80,),
        width=2,
    )
    current_y += 30

    task_area_width = panel_w - 108
    line_gap = 10
    block_gap = 22

    # Render tasks
    if tasks:
        for index, task_obj in enumerate(tasks):
            task_text = task_obj["text"]
            is_done = task_obj.get("done", False)
            
            fade = max(168, 238 - index * 18) if not is_done else max(100, 120 - index * 15)
            
            bullet_color = accent_rgb + (fade,) if not is_done else (120, 140, 160, fade)
            text_color = tuple(time_colors["text"])[:-1] + (fade,) if not is_done else (140, 160, 180, fade)
            
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
            fill=tuple(time_colors["text"])[:-1] + (185,),
            font=empty_font,
        )

    # Footer with streak if applicable
    streak = data.get("streak", 0)
    footer_parts = []
    if streak > 0:
        footer_parts.append(f"🔥 {streak} day streak")
    footer_parts.append("Updated from tasks.json")
    footer = " | ".join(footer_parts)
    
    footer_bbox = draw.textbbox((0, 0), footer, font=meta_font)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_h = footer_bbox[3] - footer_bbox[1]
    footer_x = panel_x + panel_w - 54 - footer_w
    footer_y = panel_y + panel_h - 52 - footer_h
    draw.text((footer_x, footer_y), footer, fill=tuple(time_colors["text"])[:-1] + (126,), 
             font=meta_font)

    path = str(WALLPAPER_FILE)
    # Use atomic write: save to temp file, then rename to avoid partial reads
    temp_path = str(WALLPAPER_FILE) + ".tmp.png"
    canvas.convert("RGB").save(temp_path, "PNG", quality=95)
    # Atomic rename ensures wallpaper.png is never partially written
    if Path(temp_path).exists():
        Path(temp_path).replace(Path(path))
    return path

def set_wallpaper(path):
    uri = f"file://{Path(path).resolve()}"

    commands = [
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
        ["gsettings", "set", "org.gnome.desktop.screensaver", "picture-uri", uri],
    ]

    for command in commands:
        try:
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # Silently ignore errors from gsettings (wallpaper may have changed)
            pass

def install_autostart():
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    python_executable = resolve_python_executable()
    script_path = Path(__file__).resolve()

    entry = f"""[Desktop Entry]
Type=Application
Name=Walltodo Wallpaper
Comment=Watch tasks and system wallpaper changes to keep walltodo stable
Exec={python_executable} {script_path} watch --interval 1.0
X-GNOME-Autostart-enabled=true
NoDisplay=true
"""

    AUTOSTART_FILE.write_text(entry)
    return AUTOSTART_FILE

def normalize_task(task):
    """Convert string task to object format for backward compatibility"""
    return ensure_task_object(task)

def add_task(task):
    data = load_tasks()
    # Check if task already exists and increment count
    tasks = [normalize_task(t) for t in data.get("tasks", [])]
    existing = None
    for t in tasks:
        if t["text"].lower() == task.lower():
            existing = t
            break
    
    if existing:
        existing["count"] = existing.get("count", 1) + 1
        # Reinsert
        data["tasks"] = [t for t in tasks]
    else:
        data["tasks"].append({"text": task, "done": False, "count": 1})
    
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
    last_task_mtime = None
    last_bg_path, last_bg_mtime = get_wallpaper_source_state()
    last_error_time = 0
    error_count = 0

    try:
        while True:
            try:
                current_task_mtime = TASK_FILE.stat().st_mtime
            except FileNotFoundError:
                current_task_mtime = None

            current_bg_path, current_bg_mtime = get_wallpaper_source_state()
            task_changed = current_task_mtime != last_task_mtime
            bg_changed = (
                current_bg_path != last_bg_path
                or current_bg_mtime != last_bg_mtime
            )

            if task_changed or bg_changed:
                try:
                    if update_wallpaper() is not None:
                        if task_changed and bg_changed:
                            print("Wallpaper updated from tasks.json and background change")
                        elif task_changed:
                            print("Wallpaper updated from tasks.json")
                        else:
                            print("Wallpaper updated after background change")

                    last_task_mtime = current_task_mtime
                    # Re-read after render because wallpaper is intentionally changed by walltodo.
                    last_bg_path, last_bg_mtime = get_wallpaper_source_state()
                    error_count = 0  # Reset error counter on success
                except Exception as e:
                    # Don't crash if wallpaper update fails (e.g., background changed)
                    import time as time_module
                    current_time = time_module.time()
                    # Only print error every 10 seconds to avoid spam
                    if current_time - last_error_time > 10:
                        print(f"Warning: Failed to update wallpaper: {e}")
                        last_error_time = current_time
                    error_count += 1
                    # If errors persist, wait longer before retrying
                    if error_count > 3:
                        time.sleep(interval * 2)

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

    focus_parser = subparsers.add_parser("focus", help="Show only a specific task in focus mode")
    focus_parser.add_argument("index", type=int, help="Task index (0-based)")

    layout_parser = subparsers.add_parser("layout", help="Change panel layout mode")
    layout_parser.add_argument("mode", choices=["left", "right", "minimal"], 
                              help="Layout mode: left (default), right, or minimal")

    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch tasks.json and wallpaper source changes, then refresh wallpaper"
    )
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0)"
    )

    subparsers.add_parser("clear", help="Clear all tasks")
    subparsers.add_parser("list", help="List current tasks")
    subparsers.add_parser("render", help="Render wallpaper once")
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
    elif args.command == "focus":
        data = load_tasks()
        if 0 <= args.index < len(data.get("tasks", [])):
            update_wallpaper(focus_index=args.index)
            task_obj = normalize_task(data["tasks"][args.index])
            print(f"Focus mode: {task_obj['text']}")
        else:
            parser.error(f"Task index {args.index} not found")
    elif args.command == "layout":
        config = load_config()
        config["layout"] = args.mode
        save_config(config)
        if update_wallpaper(layout=args.mode):
            print(f"Layout changed to: {args.mode}")
        else:
            parser.error("Failed to update wallpaper for new layout")
    elif args.command == "clear":
        clear_tasks()
        update_wallpaper()
        print("Cleared tasks")
    elif args.command == "list":
        list_tasks()
    elif args.command == "render":
        if update_wallpaper():
            print("Wallpaper rendered")
        else:
            parser.error("Failed to render wallpaper")
    elif args.command == "watch":
        watch_tasks(interval=args.interval)
    elif args.command == "install":
        autostart_file = install_autostart()
        print(f"Autostart installed at {autostart_file}")
    else:
        update_wallpaper()
        print("Wallpaper updated successfully")

if __name__ == "__main__":
    main()