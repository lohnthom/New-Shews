"""New Shews shortcut definitions and registration."""

import bpy


# Add shortcuts here as needed. Keymap names must match Blender's keymaps.
# Operators can be built-in or custom scripts registered from tools/.
# Check the active Blender keymap for conflicts first; see AGENTS.md.
KEYMAPS = [
    # Toggle snapping with numpad *. Scope to modeling modes so Grease Pencil
    # keeps its layer-isolation shortcut. NUMPAD_ASTERIX is Blender's spelling.
    {
        "keymap": "Object Mode",
        "space_type": "EMPTY",
        "operator": "wm.context_toggle",
        "event": {"type": "NUMPAD_ASTERIX", "value": "PRESS"},
        "properties": {"data_path": "tool_settings.use_snap"},
    },
    {
        "keymap": "Mesh",
        "space_type": "EMPTY",
        "operator": "wm.context_toggle",
        "event": {"type": "NUMPAD_ASTERIX", "value": "PRESS"},
        "properties": {"data_path": "tool_settings.use_snap"},
    },
    {
        "keymap": "Curve",
        "space_type": "EMPTY",
        "operator": "wm.context_toggle",
        "event": {"type": "NUMPAD_ASTERIX", "value": "PRESS"},
        "properties": {"data_path": "tool_settings.use_snap"},
    },
]

# Track only our items so cleanup leaves other add-ons' shortcuts intact.
_registered_keymaps = []


def register():
    unregister()
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:  # Unavailable in background mode.
        return

    for binding in KEYMAPS:
        keymap = keyconfig.keymaps.new(
            name=binding["keymap"], space_type=binding["space_type"]
        )
        item = keymap.keymap_items.new(binding["operator"], **binding["event"])
        _registered_keymaps.append((keymap, item))
        for name, value in binding.get("properties", {}).items():
            setattr(item.properties, name, value)


def unregister():
    for keymap, item in reversed(_registered_keymaps):
        keymap.keymap_items.remove(item)
    _registered_keymaps.clear()
