bl_info = {
    "name": "New Shews",
    "author": "You",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > New Shews",
    "description": "Studio tools for footwear design",
    "category": "3D View",
}

import bpy
from .tools import build_cam_rig
from .tools.texture_displacement import (
    classes as disp_classes,
    register_props as disp_register_props,
    unregister_props as disp_unregister_props,
)
from .tools.material_textures import (
    classes as mat_classes,
)
from .tools.save_export import (
    classes as export_classes,
    register_props as export_register_props,
    unregister_props as export_unregister_props,
)
from .tools.scene_utils import (
    classes as utils_classes,
)


class STUDIO_OT_create_cam_rig(bpy.types.Operator):
    bl_idname = "studio.create_cam_rig"
    bl_label = "Create CAM Rig"
    bl_description = "Create the Studio camera rig"

    def execute(self, context):
        build_cam_rig(context)
        return {"FINISHED"}


class STUDIO_OT_create_suzanne(bpy.types.Operator):
    bl_idname = "studio.create_suzanne"
    bl_label = "Create Suzanne (Temp)"
    bl_description = "Create a temporary Suzanne at fixed size and height"

    def execute(self, context):
        bpy.ops.mesh.primitive_monkey_add(size=0.13, location=(0.0, 0.0, 0.075))
        return {"FINISHED"}


class STUDIO_PT_newshews_info(bpy.types.Panel):
    bl_label = "New Shews"
    bl_idname = "STUDIO_PT_newshews_info"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "New Shews"

    def draw(self, context):
        self.layout.label(text="If nothing is selected, all is selected.", icon="INFO")


class STUDIO_PT_displacement_panel(bpy.types.Panel):
    bl_label = "Texture Displacement"
    bl_idname = "STUDIO_PT_displacement_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "New Shews"

    def draw(self, context):
        layout = self.layout
        layout.operator("studio.disp_popup", icon="TEXTURE", text="Import and Apply Texture Displacement")
        layout.operator("studio.set_displace_strength", icon="DRIVER_DISTANCE", text="Set Displacement Strength")
        layout.operator("studio.add_decimate", icon="MOD_DECIM", text="Add Decimate Modifier")


class STUDIO_PT_material_textures_panel(bpy.types.Panel):
    bl_label = "Material Textures"
    bl_idname = "STUDIO_PT_material_textures_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "New Shews"

    def draw(self, context):
        layout = self.layout
        layout.operator("studio.link_base_color", icon="NODE_TEXTURE", text="Apply Base Color")
        layout.operator("studio.link_pbr_textures", icon="MATERIAL", text="Apply PBR Textures")


class STUDIO_PT_panel(bpy.types.Panel):
    bl_label = "Studio"
    bl_idname = "STUDIO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "New Shews"

    def draw(self, context):
        layout = self.layout
        layout.operator("studio.create_cam_rig", icon="CAMERA_DATA")
        layout.operator("studio.create_suzanne", icon="MESH_MONKEY")


class STUDIO_PT_scene_utils_panel(bpy.types.Panel):
    bl_label = "Scene Utils"
    bl_idname = "STUDIO_PT_scene_utils_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "New Shews"

    def draw(self, context):
        self.layout.operator("studio.clear_parent_inverse", icon="DECORATE_OVERRIDE", text="Clear Parent Inverse")


class STUDIO_PT_save_export_panel(bpy.types.Panel):
    bl_label = "Save & Export"
    bl_idname = "STUDIO_PT_save_export_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "New Shews"

    def draw(self, context):
        layout = self.layout
        layout.operator("studio.export_obj_pick_tex_dir", icon="EXPORT", text="Export Print OBJ")
        layout.operator("studio.export_stl", icon="EXPORT", text="Export STL")


local_classes = (
    STUDIO_OT_create_cam_rig,
    STUDIO_OT_create_suzanne,
    STUDIO_PT_newshews_info,
    STUDIO_PT_displacement_panel,
    STUDIO_PT_material_textures_panel,
    STUDIO_PT_panel,
    STUDIO_PT_scene_utils_panel,
    STUDIO_PT_save_export_panel,
)


def register():
    for c in local_classes:
        bpy.utils.register_class(c)
    for c in disp_classes:
        bpy.utils.register_class(c)
    for c in mat_classes:
        bpy.utils.register_class(c)
    for c in export_classes:
        bpy.utils.register_class(c)
    for c in utils_classes:
        bpy.utils.register_class(c)
    disp_register_props()
    export_register_props()


def unregister():
    export_unregister_props()
    disp_unregister_props()
    for c in reversed(utils_classes):
        bpy.utils.unregister_class(c)
    for c in reversed(export_classes):
        bpy.utils.unregister_class(c)
    for c in reversed(mat_classes):
        bpy.utils.unregister_class(c)
    for c in reversed(disp_classes):
        bpy.utils.unregister_class(c)
    for c in reversed(local_classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()