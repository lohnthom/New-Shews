import bpy
import os
import shutil
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty


# ── Shared helper ─────────────────────────────────────────────────────────────

def _get_target_meshes(context):
    """Selected meshes, or all scene meshes if nothing is selected."""
    selected = [o for o in context.selected_objects if o.type == 'MESH']
    if not selected:
        selected = [o for o in context.scene.objects if o.type == 'MESH']
    return selected


# ── Operator 1a – Export OBJ: pick texture consolidation directory ─────────────

class STUDIO_OT_export_obj_pick_tex_dir(bpy.types.Operator):
    """Export Print OBJ – Step 1: pick folder to consolidate textures into"""
    bl_idname  = "studio.export_obj_pick_tex_dir"
    bl_label   = "Export Print OBJ"
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        directory = self.directory
        if not os.path.isdir(directory):
            self.report({'ERROR'}, f"Invalid directory: {directory}")
            return {'CANCELLED'}

        targets = _get_target_meshes(context)
        _consolidate_textures(directory, targets)

        context.scene.newshews_tex_consolidation_dir = directory
        bpy.ops.studio.export_obj_pick_file('INVOKE_DEFAULT')
        return {'FINISHED'}


# ── Operator 1b – Export OBJ: pick OBJ save location ─────────────────────────

class STUDIO_OT_export_obj_pick_file(bpy.types.Operator, ExportHelper):
    """Export Print OBJ – Step 2: choose where to save the OBJ"""
    bl_idname  = "studio.export_obj_pick_file"
    bl_label   = "Save OBJ"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".obj"
    filter_glob: StringProperty(default="*.obj", options={'HIDDEN'})

    def execute(self, context):
        filepath = self.filepath
        if not filepath.lower().endswith(".obj"):
            filepath += ".obj"

        targets      = _get_target_meshes(context)
        target_names = {o.name for o in targets}
        export_selected = len(target_names) < len(
            [o for o in context.scene.objects if o.type == 'MESH']
        )

        # Store and temporarily override unit settings
        unit_settings     = context.scene.unit_settings
        orig_system       = unit_settings.system
        orig_scale_length = unit_settings.scale_length

        unit_settings.system       = 'METRIC'
        unit_settings.scale_length = 1.0

        # If exporting a subset, select only those objects
        if export_selected:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in targets:
                obj.select_set(True)

        try:
            bpy.ops.wm.obj_export(
                filepath=filepath,
                export_selected_objects=export_selected,
                apply_modifiers=True,
                global_scale=1000.0,
                forward_axis='NEGATIVE_Z',
                up_axis='Y',
            )
            self.report({'INFO'}, f"OBJ exported to: {filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"OBJ export failed: {e}")
        finally:
            unit_settings.system       = orig_system
            unit_settings.scale_length = orig_scale_length

        return {'FINISHED'}


# ── Operator 2 – Export STL ───────────────────────────────────────────────────

class STUDIO_OT_export_stl(bpy.types.Operator, ExportHelper):
    """Export STL with applied modifiers at print scale"""
    bl_idname  = "studio.export_stl"
    bl_label   = "Export STL"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".stl"
    filter_glob: StringProperty(default="*.stl", options={'HIDDEN'})

    def execute(self, context):
        filepath = self.filepath
        if not filepath.lower().endswith(".stl"):
            filepath += ".stl"

        targets      = _get_target_meshes(context)
        target_names = {o.name for o in targets}
        export_selected = len(target_names) < len(
            [o for o in context.scene.objects if o.type == 'MESH']
        )

        if export_selected:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in targets:
                obj.select_set(True)

        try:
            bpy.ops.wm.stl_export(
                filepath=filepath,
                export_selected_objects=export_selected,
                apply_modifiers=True,
                global_scale=1000.0,
            )
            self.report({'INFO'}, f"STL exported to: {filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"STL export failed: {e}")

        return {'FINISHED'}


# ── Texture consolidation helper ──────────────────────────────────────────────

def _consolidate_textures(directory, targets):
    """
    Copy textures used by the given objects (DISPLACE modifiers +
    newshews_basecolor nodes) into the target directory and re-point
    the image datablocks to the new location.
    """
    images_to_consolidate = set()

    for obj in targets:
        # Displacement modifier textures
        for mod in obj.modifiers:
            if mod.type == 'DISPLACE' and mod.texture:
                tex = mod.texture
                if tex.type == 'IMAGE' and tex.image:
                    images_to_consolidate.add(tex.image)

        # Base color nodes
        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if not mat or not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.get("newshews_basecolor") and node.type == 'TEX_IMAGE':
                    if node.image:
                        images_to_consolidate.add(node.image)

    for image in images_to_consolidate:
        src = bpy.path.abspath(image.filepath)
        if not os.path.isfile(src):
            continue
        fname = os.path.basename(src)
        dst   = os.path.join(directory, fname)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        image.filepath = dst
        image.reload()


# ── Scene prop ────────────────────────────────────────────────────────────────

def register_props():
    bpy.types.Scene.newshews_tex_consolidation_dir = StringProperty(
        name="Texture Consolidation Dir",
        default="",
    )

def unregister_props():
    del bpy.types.Scene.newshews_tex_consolidation_dir


# ── Classes ───────────────────────────────────────────────────────────────────

classes = (
    STUDIO_OT_export_obj_pick_tex_dir,
    STUDIO_OT_export_obj_pick_file,
    STUDIO_OT_export_stl,
)