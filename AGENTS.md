# New Shews development preferences

## Shortcuts and custom scripts

- Keep shortcut definitions together in `keymaps.py`.
- Shortcuts may invoke existing Blender operators or custom New Shews operators. Put custom script logic in an appropriate module under `tools/`, expose it through a registered Blender operator, and bind that operator in `keymaps.py`. Keep script logic out of the keymap definitions.
- Before assigning or changing a shortcut, inspect the user's active Blender key configuration, including user customizations and enabled add-on bindings. Do not assume a key is free from Blender's default keymap alone.
- Check overlapping editor/mode contexts, modifiers (including wildcard modifiers), and event types such as press, release, click, and drag. Check relevant modal bindings and known macOS shortcuts when applicable. Distinguish bindings in separate contexts from actual conflicts.
- Explain what existing matching bindings do and where they apply. If a conflict exists, propose an unused alternative or discuss rearranging the existing shortcuts with the user. Do not silently replace or disable unrelated functionality.
- If the live keymap cannot be inspected, state that conflict checking is incomplete; do not claim a shortcut is unused.
- After adding a binding, verify it invokes the intended operator in its intended context and that disabling/reloading New Shews removes its bindings without duplicating them or affecting unrelated bindings.
