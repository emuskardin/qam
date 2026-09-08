# qam - quick access menu

A radial quick menu for GNOME. Open apps, folders, and commands in the same way you select weapon and potions in RPGs.

## Use it

Press **Alt+Q** to open the `qam`, click on the selected item or cycle between different wheels. 
Press it again, **Esc**, or click the center to close the menu.

| Input | Action |
|---|---|
| Click or release Alt | Pick the highlighted item |
| **1** to **9** | Pick an item by number |
| Arrow keys or scroll | Change selection |
| **Tab** | Switch wheels |
| **E** | Edit the current wheel |

## Configure it

Install from a checkout:

```sh
git clone <this repo> && cd qam
/usr/bin/python3 -m qam install
```

Use `/usr/bin/python3`. Linux distributions usually provide GTK's `gi` module
for the system Python. A virtualenv, pyenv, or another `python3` on your PATH
may report `No module named 'gi'`.

The wheel lives in `~/.config/qam/config.toml`. Edit it with:

```sh
/usr/bin/python3 -m qam edit
```

Changes load straight away. The starter config has a Main wheel for Firefox,
folders, and a terminal, plus a Dev wheel for VS Code and PyCharm.

```toml
[[wheel]]
id = "main"
name = "Main"

  [[wheel.item]]
  label = "Firefox"
  type = "app"
  value = "firefox.desktop"

  [[wheel.item]]
  label = "Documents"
  type = "path"
  value = "~/Documents"

  [[wheel.item]]
  label = "Dev"
  type = "wheel"
  value = "dev"
```

| Type | Value |
|---|---|
| `app` | A desktop-entry ID such as `firefox.desktop` or `code.desktop` |
| `command` | A program on `PATH`, such as `x-terminal-emulator` |
| `path` | A file or folder, such as `~/Downloads` |
| `uri` | A web address |
| `snippet` | Text copied to the clipboard |
| `wheel` | Another wheel ID |

Desktop entries usually live in `/usr/share/applications` or
`~/.local/share/applications`. Commands run detached. Set `shell = true` on an
item when it needs pipes, globbing, or other shell syntax.

GNOME stores the active shortcut in **Settings → Keyboard**. Set it during
installation with:

```sh
/usr/bin/python3 -m qam install --hotkey '<Super>space'
```

The `hotkey` setting in `config.toml` supplies qam's default at install time.
Check the setup with `/usr/bin/python3 -m qam doctor`. Run
`/usr/bin/python3 -m qam uninstall` to remove the service and shortcut.
