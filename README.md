# Walltodo

A beautiful task management tool that turns your desktop wallpaper into a daily intention board. Set your tasks via CLI and watch them appear on your GNOME wallpaper with automatic updates.

![Walltodo Demo](wallpaper.png)

## Features

✨ **Beautiful Wallpaper Rendering** - Tasks are rendered directly on your wallpaper with smooth typography and elegant styling  
✓ **Task Status Tracking** - Mark tasks as complete to get visual feedback and motivation  
🎨 **Progressive Styling** - Tasks fade elegantly, with completed tasks shown with checkmarks and strikethrough  
⚡ **Live Updates** - Wallpaper automatically refreshes when tasks change  
🚀 **CLI Commands** - Full control from the terminal to add, edit, remove, and mark tasks  
🔄 **Autostart Support** - Install as a login autostart application on GNOME Desktop  
📊 **Progress Tracking** - See your completion progress in the terminal  

## Installation

### Prerequisites

- Python 3.7+
- GNOME Desktop (Ubuntu 20.04+)
- PIL/Pillow for image manipulation
- Required system packages:

```bash
sudo apt-get install python3-pip python3-venv
```

### Setup

1. Clone or download the repository:
```bash
cd ~/Downloads/walltodo
```

2. Create and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install Pillow
```

4. Make the script executable:
```bash
chmod +x walltodo.py
```

5. Install as autostart (optional):
```bash
python walltodo.py install
```

## Usage

### Basic Commands

**Add a task:**
```bash
python walltodo.py add "Complete the project"
python walltodo.py add "Review pull requests"
```

**List all tasks with status:**
```bash
python walltodo.py list
```

Output:
```
Today's Intent
1. [○] Complete the project
2. [✓] Review pull requests

Progress: 1/2 tasks completed
```

**Mark a task as done:**
```bash
python walltodo.py done 0  # Mark first task as complete
python walltodo.py done 1  # Toggle second task (undo if already done)
```

**Edit a task:**
```bash
python walltodo.py edit 0 "New task text"
```

**Remove a task:**
```bash
python walltodo.py remove 1  # Remove second task
```

**Clear all tasks:**
```bash
python walltodo.py clear
```

**Set a custom title:**
```bash
python walltodo.py title "This Week's Goals"
```

**Render wallpaper once:**
```bash
python walltodo.py render
```

**Watch for changes and auto-refresh:**
```bash
python walltodo.py watch
```

Press `Ctrl+C` to stop watching.

## Command Reference

| Command | Arguments | Description |
|---------|-----------|-------------|
| `add` | `<task-text>` | Add a new task |
| `list` | - | List all tasks with completion status |
| `done` | `<index>` | Toggle a task as done/undone (0-based) |
| `edit` | `<index> <new-text>` | Edit a task at the given index |
| `remove` | `<index>` | Remove a task at the given index |
| `title` | `<title-text>` | Set the wallpaper title |
| `clear` | - | Remove all tasks |
| `render` | - | Render wallpaper once |
| `watch` | - | Watch tasks.json and auto-refresh |
| `install` | - | Install as GNOME autostart application |

## Task Status System

### Status Indicators

- **○** - Task not completed
- **✓** - Task completed

### Visual Representation

On the wallpaper:
- Incomplete tasks appear in bright, vibrant colors
- Completed tasks show a checkmark (✓) bullet and appear dimmed
- Completed tasks are shown with a strikethrough line

### Motivation Features

- **Progress Tracking**: Terminal shows your completion percentage
- **Visual Feedback**: See completed tasks immediately on your wallpaper
- **Strikethrough Effect**: Visually satisfying completion indicator
- **Dimmed Styling**: Completed tasks fade into the background

## Configuration

### Tasks File

Tasks are stored in `tasks.json` in the same directory as `walltodo.py`:

```json
{
  "title": "Today's Intent",
  "tasks": [
    {
      "text": "Complete the project",
      "done": false
    },
    {
      "text": "Review pull requests",
      "done": true
    }
  ]
}
```

### Customization

Edit `walltodo.py` to customize:

```python
WIDTH, HEIGHT = 1920, 1080  # Wallpaper resolution
BG_COLOR = "#0b0f19"        # Background color
MAX_TASKS = 5               # Maximum tasks to display
```

## Autostart

Install Walltodo to launch automatically on login:

```bash
python walltodo.py install
```

This creates a `.desktop` entry in `~/.config/autostart/walltodo.desktop` that will:
- Run on every GNOME session login
- Update your wallpaper with your tasks
- Work regardless of where you run the script from

To uninstall, simply remove:
```bash
rm ~/.config/autostart/walltodo.desktop
```

## Wallpaper Sources

Walltodo renders on top of your current GNOME wallpaper. It fetches the wallpaper from:
- `org.gnome.desktop.background.picture-uri-dark` (preferred for dark mode)
- `org.gnome.desktop.background.picture-uri` (fallback)

If no wallpaper is set, it uses a default dark background.

## Troubleshooting

### Wallpaper not updating?

1. Ensure GNOME is installed:
```bash
gsettings list-schemas | grep gnome.desktop.background
```

2. Force a refresh:
```bash
python walltodo.py render
```

3. Watch for changes:
```bash
python walltodo.py watch
```

### Tasks.json not found?

The first time you add a task, `tasks.json` will be created automatically:
```bash
python walltodo.py add "First task"
```

### Font issues?

If you see default system fonts, install TrueType fonts:
```bash
sudo apt-get install fonts-dejavu
```

## Development

### Project Structure

```
walltodo/
├── walltodo.py          # Main script
├── tasks.json           # Task storage
├── wallpaper.png        # Generated wallpaper
└── README.md            # This file
```

### Key Functions

- `load_tasks()` - Load tasks from JSON
- `generate_wallpaper()` - Render tasks to image
- `set_wallpaper()` - Update GNOME wallpaper
- `add_task()`, `edit_task()`, `toggle_task()`, `remove_task()` - Task operations
- `watch_tasks()` - Monitor tasks.json for changes
- `install_autostart()` - Install GNOME autostart

## Tips & Tricks

**Create daily task aliases:**
```bash
alias walltodo='python ~/walltodo/walltodo.py'

# Then use:
walltodo add "Task"
walltodo list
walltodo done 0
```

**Quick task marking:**
```bash
walltodo add "Important task" && walltodo done 0  # Add and mark done immediately
```

**Automated watch mode:**
```bash
# In .bashrc or .zshrc:
watch_walltodo() {
    cd ~/walltodo && python walltodo.py watch
}
```

## Contributing

Feel free to fork and improve! Some ideas:
- Multi-user support
- Wayland support
- Custom themes
- Task priorities
- Recurring tasks

## License

MIT License - feel free to use and modify!

## Motivation

This project combines productivity with aesthetics. By making your tasks visible on your wallpaper, you get constant gentle reminders of your daily intentions without needing to open another application. The completion tracking provides psychological motivation to finish your goals.

Stay motivated, and build your day intentionally! 🚀
