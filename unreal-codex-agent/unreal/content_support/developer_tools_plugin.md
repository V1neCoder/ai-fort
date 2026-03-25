# Developer Tools Plugin

## Purpose

This optional Unreal Editor plugin scaffold makes the developer x-ray flow feel built into Unreal instead of like a loose external report.

It does not replace the working Python helper pipeline.
It gives you a dockable Unreal panel that can:

- open the latest generated x-ray HTML
- open the session folder
- open the project config
- hide or show the list of tool capabilities inside the panel

## Plugin location

The scaffold lives at:

`unreal/plugin/UCADeveloperTools`

To try it in a real Unreal project, copy that folder into:

`<YourUnrealProject>/Plugins/UCADeveloperTools`

Then regenerate project files and rebuild the editor target.

## How it fits the repo

The repo already writes x-ray artifacts here:

`data/sessions/<session_id>/developer_xray/current.html`

The plugin simply gives you a built-in Unreal tab for opening those artifacts and working with them in a more editor-native way.

## Repo root resolution

The panel looks for the repo in this order:

1. `UCA_REPO_ROOT` environment variable
2. walking upward from the Unreal project directory until it finds a folder containing `data/sessions`

If your Unreal project and repo are not nested together, set `UCA_REPO_ROOT`.

## Tool list visibility

There are now two ways to hide the list of available developer tool actions:

### In the generated x-ray HTML

Use the `Hide Tool List` button in the viewer.
That state is persisted in local storage.

### In project config

Set:

`developer_tools.scene_xray.default_show_tool_list`

to `false` in `config/project.json`

Or run:

`python -m apps.mcp_extensions.developer_tools set-defaults --repo-root . --show-tool-list false`

## What this plugin does not do yet

- it does not embed a full browser widget
- it does not execute Python helper commands directly inside Unreal
- it does not recolor the live viewport yet

Those are deliberate boundaries so the current working scaffold stays stable.

## Good next steps

If you want to push this farther later:

- add a browser panel that renders `current.html` inline
- add Python execution buttons for `scene-xray`
- add editor overlays or debug drawing for green/red in-world identification
- bind the panel to live Unreal selection changes
