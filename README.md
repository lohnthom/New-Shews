# New Shews

Footwear studio tools in **3D Viewport → Sidebar (N) → New Shews**.
**3D Print Prep** groups the collapsible **Texture Displacement**, **Material Textures**, and **Save & Export** subpanels. **Studio**, **Curve Tools**, and **Scene Utils** are separate top-level panels.
The add-on declares Blender 4.0 or later; the local development installation uses Blender 5.2.1.

## Existing tools

- **Texture Displacement:** choose a texture folder, match `<Material>_Displacement` images, and add/replace `NewShews_Subdivide` (Catmull–Clark, levels 2–5, default 3) followed by `NewShews_Displace` (UV coordinates, midpoint 0.5, default strength 1.2). Separate commands update displacement strength or append a Decimate modifier. Decimate uses Blender's defaults; adjust its ratio afterward.
- **Material Textures:** match `<Material>_BaseColor`, or separately `<Material>_Metallic`, `<Material>_Roughness`, and `<Material>_Normal`. Build UV → Mapping → Image nodes feeding a Principled BSDF, with a Normal Map node for normals. Base color uses sRGB; the other maps use Non-Color. Reapplying replaces nodes tagged by the corresponding New Shews tool.
- **Studio:** create a `STUDIO/CAM_Rig` collection containing a pivot, camera-position and target controls, tracking constraint, and focal-length handle. Drivers constrain the lens to 18–200 mm and compensate camera distance. A separate command creates a small temporary Suzanne mesh.
- **Scene Utils:** reset parent-inverse matrices to identity. This can change the visible transform of parented objects.
- **Curve Tools → Rebuild Curve:** choose a control-point count and output type (NURBS by default, Bézier, or Poly) for selected splines. The result stays editable in Edit Mode and supports Undo.
- **Save & Export:** export OBJ or STL with evaluated modifiers at a fixed scale factor of 1000. OBJ first copies displacement and New Shews base-color textures into a chosen folder and repoints the scene's image paths; it then opens the OBJ save picker. OBJ uses -Z forward and Y up and temporarily sets metric units with unit scale 1, restoring them afterward.

Texture matching is case-insensitive and uses the object's **first material slot**. Supported image extensions are PNG, JPG/JPEG, TIF/TIFF, and EXR. For example, material `Sole` matches `Sole_BaseColor.png` and `Sole_Displacement.exr`.

The mesh tools use selected meshes, falling back to **all scene meshes if no mesh is selected**, including when only a camera or empty is selected. Clear Parent Inverse uses selected objects, then the active object, then all scene objects.

## Current limitations

- Creating a camera rig does not assign the new camera as the scene's active render camera. The focal drivers use world-space Y positions, so pivot rotation can affect the lens.
- Material changes affect every object sharing that material. UV maps and an existing first material are expected.
- OBJ texture consolidation does not include metallic, roughness, or normal textures. Equal filenames from different source directories can overwrite one another in the destination. Consolidation happens before the OBJ save dialog, so cancelling that dialog does not undo it.
- Subset exports change object selection without restoring it. Export errors are reported, but the operators still return `FINISHED`. A scale factor of 1000 assumes the source geometry's coordinates are suitable for that print workflow.

## Rebuild Curve

1. Select a curve object and enter Edit Mode.
2. Select at least one control point on each spline you want to rebuild. Each selected spline is rebuilt in full; unselected splines are preserved.
3. Open **New Shews → Curve Tools → Rebuild Curve**.
4. Set **Point Count** (per spline, 2–512) and **Curve Type**, then confirm.

The rebuilt points are selected, and Blender remains in Edit Mode. Closed splines remain closed and require at least three points. Multiple curve objects in Edit Mode are supported.

NURBS output fits a curve of up to cubic degree with uniform weights; open endpoints are fixed to the source curve's evaluated endpoints. Bézier output uses evenly spaced anchors and automatic handles; Poly output uses straight segments. Sampling distances account for object scale. This is an approximation: reducing the point count, rebuilding sharp corners, or replacing weighted NURBS can alter the shape. Radius and tilt profiles are interpolated over the original control-point sequence and are also approximate.

The tool operates on the editable base spline, before Geometry Nodes or other modifiers. Object transforms, materials, bevel settings, and modifiers remain on the object. It supports legacy Curve objects with NURBS, Bézier, or Poly splines; it does not bake procedural output or operate on newer hair/Curves objects, surfaces, or text. Curves with shape keys or animated curve data are rejected because changing their topology would invalidate that data. Linked objects sharing the same curve datablock share the rebuilt geometry, as with ordinary Edit Mode changes.

## Development installation on this Mac

The development branch is `codex/development-setup`. Blender discovers the repository under the Python module name `newshews` through this symbolic link:

```text
~/Library/Application Support/Blender/5.2/scripts/addons/newshews
  → this New Shews repository
```

To create the link on this Mac if it is absent:

```sh
ln -s '/Users/lt/Library/Mobile Documents/com~apple~CloudDocs/Lohnny/Creative Projects/3D/Blender/addons/New Shews' \
  "$HOME/Library/Application Support/Blender/5.2/scripts/addons/newshews"
```

Enable **New Shews** in Blender Preferences → Add-ons and save preferences. Avoid enabling a second installed copy of the same add-on, since its operator and panel identifiers would collide. Use the checkbox to disable it while developing: **Uninstall/Remove deletes the add-on's files**, and a directly discovered source folder can include your entire Git repository. Keep commits pushed to GitHub as a recovery copy.

This Mac also discovers the repository through an existing custom scripts path, so Preferences currently shows two New Shews entries. Expand each entry to inspect its **File** path. Enable only the one ending in `Blender/5.2/scripts/addons/newshews/__init__.py`; leave the direct `New Shews/__init__.py` entry disabled and do not uninstall it.

Edits and branch switches change the files Blender will load. Python modules already loaded in a running Blender session remain in memory: save your scene and restart Blender to reliably load all edited modules, including files under `tools/`.

In Blender's Python Console, verify the resolved source path with:

```python
import newshews, os
print(os.path.realpath(newshews.__file__))
```

It should print this repository's `__init__.py`. A future Blender version needs its own add-ons link and enablement.

Setup verification: Blender 5.2.1 passed an isolated enable → disable → re-enable check, including panel/property registration and source-path verification. The linked entry was also enabled in the interactive session and preferences were saved. Individual modeling/export operations have not been exhaustively tested.

## Repository layout

- `__init__.py`: sidebar panels, studio operators, and registration.
- `keymaps.py`: shortcut definitions in `KEYMAPS`, plus registration and cleanup. Each entry specifies an operator, editor/mode, key combination, and optional operator properties.
- `tools/cam_rig.py`: camera rig construction and drivers.
- `tools/texture_displacement.py`: texture matching and geometry modifiers.
- `tools/material_textures.py`: base-color and PBR material nodes.
- `tools/scene_utils.py`: parent-inverse utility.
- `tools/curve_rebuild.py`: selected-spline sampling, fitting, and the rebuild dialog.
- `tools/save_export.py`: texture consolidation and OBJ/STL export.
- `tests/test_curve_rebuild.py`: Blender integration tests for types, point counts, endpoints, closed loops, selection, preservation, and validation.

`.gitignore` excludes macOS metadata, Python bytecode, and Blender backup files. Original `.blend` files and texture assets remain trackable.

## Adding shortcuts

**Numpad `*`** toggles snapping in **Object Mode**, **mesh Edit Mode**, and **curve Edit Mode** (Bezier/NURBS) in the 3D Viewport. Grease Pencil's layer-isolation binding and modified numpad shortcuts remain intact. Blender's existing Shift+Tab snapping shortcut also remains available. The new binding does not change shortcuts during an active transform or in other edit modes.

Shortcuts can run built-in Blender commands or custom scripts. Custom script logic belongs under `tools/`, exposed through a registered Blender operator; `keymaps.py` maps the key combination to that operator.

Before adding a shortcut, inspect the active Blender keymap, including user customizations and enabled add-ons, for overlapping bindings in the intended editor and mode. Explain any existing functionality on those keys, then choose an unused combination or discuss rearranging the bindings. The ongoing development instructions are recorded in `AGENTS.md`.
