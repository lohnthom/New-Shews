import bpy
import mathutils


def _get_targets(context):
    selected = [o for o in context.selected_objects]
    if not selected and context.active_object:
        selected = [context.active_object]
    if not selected:
        selected = list(context.scene.objects)
    return selected


class STUDIO_OT_clear_parent_inverse(bpy.types.Operator):
    bl_idname = "studio.clear_parent_inverse"
    bl_label = "Clear Parent Inverse"
    bl_description = "Reset matrix_parent_inverse to identity on target objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        targets = _get_targets(context)
        if not targets:
            self.report({"WARNING"}, "No objects found.")
            return {"CANCELLED"}

        for obj in targets:
            obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)

        self.report({"INFO"}, f"Parent inverse cleared on {len(targets)} object(s).")
        return {"FINISHED"}


classes = (
    STUDIO_OT_clear_parent_inverse,
)