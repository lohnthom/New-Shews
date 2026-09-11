import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, IntProperty, FloatProperty


# ── Scene props ───────────────────────────────────────────────────────────────

def register_props():
    bpy.types.Scene.lohnny_disp_subdivisions = IntProperty(
        name="Subdivisions",
        description="Subdivision level applied to each displaced object",
        default=3, min=2, max=5,
    )
    bpy.types.Scene.lohnny_disp_strength = FloatProperty(
        name="Strength",
        description="Displace modifier strength",
        default=1.2, min=0.0, soft_max=5.0, step=1, precision=3,
    )

def unregister_props():
    del bpy.types.Scene.lohnny_disp_subdivisions
    del bpy.types.Scene.lohnny_disp_strength


# ── Shared helper ─────────────────────────────────────────────────────────────

def _get_target_meshes(context):
    """Selected meshes, or all scene meshes if nothing is selected."""
    selected = [o for o in context.selected_objects if o.type == 'MESH']
    if not selected:
        selected = [o for o in context.scene.objects if o.type == 'MESH']
    return selected


# ── Operator 1 – Popup dialog ─────────────────────────────────────────────────

class STUDIO_OT_disp_popup(bpy.types.Operator):
    """Import displacement textures and apply to meshes"""
    bl_idname  = "studio.disp_popup"
    bl_label   = "Import and Apply Texture Displacement"
    bl_options = {'REGISTER', 'UNDO'}

    subdivisions: IntProperty(name="Subdivisions", default=3, min=2, max=5)
    strength: FloatProperty(name="Strength", default=1.2, min=0.0,
                            soft_max=5.0, step=1, precision=3)

    def invoke(self, context, event):
        self.subdivisions = context.scene.lohnny_disp_subdivisions
        self.strength     = context.scene.lohnny_disp_strength
        return context.window_manager.invoke_props_dialog(self, width=260)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "subdivisions")
        layout.prop(self, "strength")

    def execute(self, context):
        context.scene.lohnny_disp_subdivisions = self.subdivisions
        context.scene.lohnny_disp_strength     = self.strength
        bpy.ops.studio.disp_pick_dir('INVOKE_DEFAULT')
        return {'FINISHED'}


# ── Operator 2 – Directory picker ─────────────────────────────────────────────

class STUDIO_OT_disp_pick_dir(bpy.types.Operator, ImportHelper):
    """Pick the folder containing displacement textures"""
    bl_idname  = "studio.disp_pick_dir"
    bl_label   = "Select Texture Directory"
    bl_options = {'REGISTER', 'UNDO'}

    filename:          StringProperty(default="")
    filter_glob:       StringProperty(default="*", options={'HIDDEN'})
    use_filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    def execute(self, context):
        directory = os.path.dirname(self.filepath)
        if not os.path.isdir(directory):
            self.report({'ERROR'}, f"Invalid directory: {directory}")
            return {'CANCELLED'}

        subdivisions = context.scene.lohnny_disp_subdivisions
        strength     = context.scene.lohnny_disp_strength
        targets      = _get_target_meshes(context)

        if not targets:
            self.report({'WARNING'}, "No mesh objects found in scene.")
            return {'CANCELLED'}

        texture_map = _build_texture_map(directory)
        skipped, matched = [], []

        for obj in targets:
            mat_name = _get_material_name(obj)
            if mat_name is None:
                skipped.append(f"{obj.name} (no material)")
                continue
            tex_path = texture_map.get(mat_name.lower())
            if tex_path is None:
                skipped.append(f"{obj.name} (no texture for '{mat_name}')")
                continue
            _setup_object(obj, tex_path, subdivisions, strength)
            matched.append(obj.name)

        if matched:
            msg = f"Displacement applied to: {', '.join(matched)}"
            if skipped:
                msg += f" | Skipped: {', '.join(skipped)}"
            self.report({'INFO'}, msg)
        else:
            self.report({'WARNING'}, "No objects matched. Skipped: " + ", ".join(skipped))

        return {'FINISHED'}


# ── Operator 3 – Set Displacement Strength ────────────────────────────────────

class STUDIO_OT_set_displace_strength(bpy.types.Operator):
    """Set the strength of NewShews_Displace on target objects"""
    bl_idname  = "studio.set_displace_strength"
    bl_label   = "Set Displacement Strength"
    bl_options = {'REGISTER', 'UNDO'}

    strength: FloatProperty(name="Strength", default=1.2, min=0.0,
                            soft_max=5.0, step=1, precision=3)

    def invoke(self, context, event):
        self.strength = context.scene.lohnny_disp_strength
        return context.window_manager.invoke_props_dialog(self, width=260)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "strength")

    def execute(self, context):
        targets = _get_target_meshes(context)
        if not targets:
            self.report({'WARNING'}, "No mesh objects found in scene.")
            return {'CANCELLED'}

        updated, skipped = [], []
        for obj in targets:
            mod = obj.modifiers.get("NewShews_Displace")
            if mod:
                mod.strength = self.strength
                updated.append(obj.name)
            else:
                skipped.append(obj.name)

        if updated:
            msg = f"Strength updated on: {', '.join(updated)}"
            if skipped:
                msg += f" | No NewShews_Displace on: {', '.join(skipped)}"
            self.report({'INFO'}, msg)
        else:
            self.report({'WARNING'}, "No objects have a NewShews_Displace modifier.")

        return {'FINISHED'}


# ── Operator 4 – Add Decimate ─────────────────────────────────────────────────

class STUDIO_OT_add_decimate(bpy.types.Operator):
    """Add a Decimate modifier to target mesh objects"""
    bl_idname  = "studio.add_decimate"
    bl_label   = "Add Decimate Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        targets = _get_target_meshes(context)
        if not targets:
            self.report({'WARNING'}, "No mesh objects found in scene.")
            return {'CANCELLED'}

        for obj in targets:
            obj.modifiers.new(name="NewShews_Decimate", type='DECIMATE')

        self.report({'INFO'}, f"Decimate modifier added to {len(targets)} object(s).")
        return {'FINISHED'}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_texture_map(directory):
    EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr'}
    result = {}
    for fname in os.listdir(directory):
        name, ext = os.path.splitext(fname)
        if ext.lower() not in EXTENSIONS:
            continue
        if '_' not in name:
            continue
        parts = name.rsplit('_', 1)
        if parts[1].lower() == 'displacement':
            result[parts[0].lower()] = os.path.join(directory, fname)
    return result


def _get_material_name(obj):
    if obj.data.materials and obj.data.materials[0] is not None:
        return obj.data.materials[0].name
    return None


def _get_or_load_image(filepath):
    name = os.path.basename(filepath)
    if name in bpy.data.images:
        img = bpy.data.images[name]
        if bpy.path.abspath(img.filepath) == bpy.path.abspath(filepath):
            return img
    return bpy.data.images.load(filepath)


def _setup_object(obj, tex_path, subdivisions, strength):
    _setup_subdivision_modifier(obj, subdivisions)
    _setup_displace_modifier(obj, tex_path, strength)

    mod_names    = [m.name for m in obj.modifiers]
    subsurf_idx  = mod_names.index("NewShews_Subdivide")
    displace_idx = mod_names.index("NewShews_Displace")
    target_idx   = subsurf_idx + 1

    if displace_idx != target_idx:
        with bpy.context.temp_override(object=obj):
            bpy.ops.object.modifier_move_to_index(
                modifier="NewShews_Displace", index=target_idx
            )


def _setup_subdivision_modifier(obj, subdivisions):
    MOD_NAME = "NewShews_Subdivide"
    if MOD_NAME in obj.modifiers:
        obj.modifiers.remove(obj.modifiers[MOD_NAME])
    mod = obj.modifiers.new(name=MOD_NAME, type='SUBSURF')
    mod.subdivision_type = 'CATMULL_CLARK'
    mod.levels           = subdivisions
    mod.render_levels    = subdivisions


def _setup_displace_modifier(obj, tex_path, strength):
    MOD_NAME = "NewShews_Displace"
    if MOD_NAME in obj.modifiers:
        obj.modifiers.remove(obj.modifiers[MOD_NAME])

    image = _get_or_load_image(tex_path)
    image.colorspace_settings.name = 'Non-Color'

    tex_name = f"NewShews_{os.path.basename(tex_path)}"
    if tex_name in bpy.data.textures:
        tex = bpy.data.textures[tex_name]
    else:
        tex = bpy.data.textures.new(name=tex_name, type='IMAGE')

    tex.image = image

    mod = obj.modifiers.new(name=MOD_NAME, type='DISPLACE')
    mod.texture        = tex
    mod.texture_coords = 'UV'
    mod.strength       = strength
    mod.mid_level      = 0.5


# ── Classes ───────────────────────────────────────────────────────────────────

classes = (
    STUDIO_OT_disp_popup,
    STUDIO_OT_disp_pick_dir,
    STUDIO_OT_set_displace_strength,
    STUDIO_OT_add_decimate,
)