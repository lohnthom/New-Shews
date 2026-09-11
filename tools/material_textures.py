import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty


def _get_target_meshes(context):
    selected = [o for o in context.selected_objects if o.type == "MESH"]
    if not selected:
        selected = [o for o in context.scene.objects if o.type == "MESH"]
    return selected


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


def _scan_directory(directory, suffix):
    EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr"}
    result = {}
    for fname in os.listdir(directory):
        name, ext = os.path.splitext(fname)
        if ext.lower() not in EXTENSIONS:
            continue
        if "_" not in name:
            continue
        parts = name.rsplit("_", 1)
        if parts[1].lower() == suffix.lower():
            result[parts[0].lower()] = os.path.join(directory, fname)
    return result


def _ensure_bsdf_and_output(mat):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (300, 300)

    output_node = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None)
    if output_node is None:
        output_node = nodes.new("ShaderNodeOutputMaterial")
        output_node.location = (600, 300)
    if not output_node.inputs["Surface"].is_linked:
        links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

    return bsdf, output_node


def _make_tex_coord_chain(mat, bsdf, tag, y_offset):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    def make(node_type, x, y):
        n = nodes.new(node_type)
        n[tag] = True
        n.location = (x, y)
        return n

    x = bsdf.location[0]
    y = bsdf.location[1] + y_offset

    tex_coord = make("ShaderNodeTexCoord", x - 800, y)
    mapping = make("ShaderNodeMapping", x - 580, y)
    tex_image = make("ShaderNodeTexImage", x - 330, y)

    mapping.vector_type = "POINT"
    tex_image.interpolation = "Linear"
    tex_image.projection = "FLAT"
    tex_image.extension = "REPEAT"

    links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex_image.inputs["Vector"])

    return tex_image


class STUDIO_OT_link_base_color(bpy.types.Operator, ImportHelper):
    bl_idname = "studio.link_base_color"
    bl_label = "Select Texture Directory"
    bl_options = {"REGISTER", "UNDO"}

    filename: StringProperty(default="")
    filter_glob: StringProperty(default="*", options={"HIDDEN"})
    use_filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        directory = os.path.dirname(self.filepath)
        if not os.path.isdir(directory):
            self.report({"ERROR"}, f"Invalid directory: {directory}")
            return {"CANCELLED"}

        targets = _get_target_meshes(context)
        texture_map = _scan_directory(directory, "BaseColor")
        matched, skipped = [], []

        for obj in targets:
            mat_name = _get_material_name(obj)
            if mat_name is None:
                skipped.append(f"{obj.name} (no material)")
                continue
            tex_path = texture_map.get(mat_name.lower())
            if tex_path is None:
                skipped.append(f"{obj.name} (no texture for '{mat_name}')")
                continue
            _apply_base_color(obj, tex_path)
            matched.append(obj.name)

        if matched:
            msg = f"Base color linked on: {', '.join(matched)}"
            if skipped:
                msg += f" | Skipped: {', '.join(skipped)}"
            self.report({"INFO"}, msg)
        else:
            self.report({"WARNING"}, "No objects matched. Skipped: " + ", ".join(skipped))

        return {"FINISHED"}


def _apply_base_color(obj, tex_path):
    mat = obj.data.materials[0]
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf, _ = _ensure_bsdf_and_output(mat)

    for n in list(nodes):
        if n.get("newshews_basecolor"):
            nodes.remove(n)

    image = _get_or_load_image(tex_path)
    image.colorspace_settings.name = "sRGB"

    tex_image = _make_tex_coord_chain(mat, bsdf, "newshews_basecolor", y_offset=0)
    tex_image.image = image
    links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])


class STUDIO_OT_link_pbr_textures(bpy.types.Operator, ImportHelper):
    bl_idname = "studio.link_pbr_textures"
    bl_label = "Select Texture Directory"
    bl_options = {"REGISTER", "UNDO"}

    filename: StringProperty(default="")
    filter_glob: StringProperty(default="*", options={"HIDDEN"})
    use_filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        directory = os.path.dirname(self.filepath)
        if not os.path.isdir(directory):
            self.report({"ERROR"}, f"Invalid directory: {directory}")
            return {"CANCELLED"}

        targets = _get_target_meshes(context)
        metal_map = _scan_directory(directory, "Metallic")
        rough_map = _scan_directory(directory, "Roughness")
        normal_map = _scan_directory(directory, "Normal")
        matched, skipped = [], []

        for obj in targets:
            mat_name = _get_material_name(obj)
            if mat_name is None:
                skipped.append(f"{obj.name} (no material)")
                continue

            key = mat_name.lower()
            if not any([key in metal_map, key in rough_map, key in normal_map]):
                skipped.append(f"{obj.name} (no PBR textures for '{mat_name}')")
                continue

            _apply_pbr_textures(
                obj,
                metal_path=metal_map.get(key),
                rough_path=rough_map.get(key),
                normal_path=normal_map.get(key),
            )
            matched.append(obj.name)

        if matched:
            msg = f"PBR textures linked on: {', '.join(matched)}"
            if skipped:
                msg += f" | Skipped: {', '.join(skipped)}"
            self.report({"INFO"}, msg)
        else:
            self.report({"WARNING"}, "No objects matched. Skipped: " + ", ".join(skipped))

        return {"FINISHED"}


def _apply_pbr_textures(obj, metal_path, rough_path, normal_path):
    mat = obj.data.materials[0]
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf, _ = _ensure_bsdf_and_output(mat)

    for n in list(nodes):
        if n.get("newshews_metallic") or n.get("newshews_roughness") or n.get("newshews_normal"):
            nodes.remove(n)

    x = bsdf.location[0]

    if metal_path:
        image = _get_or_load_image(metal_path)
        image.colorspace_settings.name = "Non-Color"
        tex = _make_tex_coord_chain(mat, bsdf, "newshews_metallic", y_offset=-300)
        tex.image = image
        links.new(tex.outputs["Color"], bsdf.inputs["Metallic"])

    if rough_path:
        image = _get_or_load_image(rough_path)
        image.colorspace_settings.name = "Non-Color"
        tex = _make_tex_coord_chain(mat, bsdf, "newshews_roughness", y_offset=-600)
        tex.image = image
        links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])

    if normal_path:
        image = _get_or_load_image(normal_path)
        image.colorspace_settings.name = "Non-Color"
        tex = _make_tex_coord_chain(mat, bsdf, "newshews_normal", y_offset=-900)
        tex.image = image

        normal_node = nodes.new("ShaderNodeNormalMap")
        normal_node["newshews_normal"] = True
        normal_node.location = (x - 100, bsdf.location[1] - 900)

        links.new(tex.outputs["Color"], normal_node.inputs["Color"])
        links.new(normal_node.outputs["Normal"], bsdf.inputs["Normal"])


classes = (
    STUDIO_OT_link_base_color,
    STUDIO_OT_link_pbr_textures,
)