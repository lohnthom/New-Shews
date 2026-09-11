import bpy
from math import radians


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def get_or_create_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        if parent:
            parent.children.link(coll)
        else:
            bpy.context.scene.collection.children.link(coll)
    return coll


def link_to_collection(obj, coll):
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    for c in obj.users_collection:
        if c != coll:
            c.objects.unlink(obj)


def empty(name, type='PLAIN_AXES', loc=(0,0,0), size=0.03, coll=None):
    bpy.ops.object.empty_add(type=type, location=loc)
    o = bpy.context.object
    o.name = name
    o.empty_display_size = size
    if coll:
        link_to_collection(o, coll)
    return o


# --------------------------------------------------
# Core CAM_Rig builder
# --------------------------------------------------

def build_cam_rig(context):

    scene = context.scene

    # --- Collections ---
    studio_coll = get_or_create_collection("STUDIO")
    cam_coll = bpy.data.collections.new("CAM_Rig")
    studio_coll.children.link(cam_coll)
    cam_coll.color_tag = 'COLOR_01'

    # --- Config ---
    FOCAL_START_MM = 50.0
    FOCAL_MIN_MM   = 18.0
    FOCAL_MAX_MM   = 200.0
    MM_PER_M       = 100.0

    CAM_POS_START = (0.0, -0.53, 0.10)
    CAM_TGT_Z     = 0.07

    bpy.ops.object.select_all(action='DESELECT')

    # --- CAM_pivot (circle mesh) ---
    bpy.ops.mesh.primitive_circle_add(
        radius=0.175,
        vertices=64,
        location=(0,0,0)
    )
    pivot = context.object
    pivot.name = "CAM_pivot"
    pivot.hide_render = True
    pivot.show_in_front = True
    pivot.display_type = 'WIRE'

    pivot.lock_location = (True, True, True)
    pivot.lock_scale    = (True, True, True)
    pivot.lock_rotation = (False, True, False)

    link_to_collection(pivot, cam_coll)

    # --- CAM_pos ---
    cam_pos = empty(
        "CAM_pos",
        'PLAIN_AXES',
        CAM_POS_START,
        0.03,
        cam_coll
    )
    cam_pos.lock_location[0] = True
    cam_pos.parent = pivot

    # --- CAM_target ---
    cam_target = empty(
        "CAM_target",
        'SPHERE',
        (0,0,CAM_TGT_Z),
        0.03,
        cam_coll
    )

    # --- CAM_aim ---
    cam_aim = empty("CAM_aim", 'PLAIN_AXES', (0,0,0), 0.01, cam_coll)
    cam_aim.parent = cam_pos
    cam_aim.hide_select = True

    track = cam_aim.constraints.new('TRACK_TO')
    track.target = cam_target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    # --- CAM_focal ---
    cam_focal = empty("CAM_focal", 'PLAIN_AXES', (0,0,0), 0.01, cam_coll)
    cam_focal.parent = cam_aim
    cam_focal.hide_select = True

    # --- Camera ---
    bpy.ops.object.camera_add(location=(0,0,0))
    cam = context.object
    cam.name = "CAM"
    cam.parent = cam_focal
    cam.rotation_euler = (0,0,0)

    cam.data.lens_unit = 'MILLIMETERS'
    cam.data.lens = FOCAL_START_MM
    cam.data.display_size = 0.25

    cam.hide_select = True
    link_to_collection(cam, cam_coll)

    # --- Safe Areas ---
    cam.data.show_safe_areas = True
    scene.safe_areas.title[:]  = (0.0, 0.0)
    scene.safe_areas.action[:] = (0.15, 0.20)

    # --- FOCAL_handle ---
    focal = empty(
        "FOCAL_handle",
        'CONE',
        (0, CAM_POS_START[1], 0),
        0.03,
        cam_coll
    )
    focal.lock_location[0] = True
    focal.lock_location[2] = True
    focal.parent = pivot

    # --- Limit handle movement ---
    limit = focal.constraints.new('LIMIT_LOCATION')
    limit.use_min_x = limit.use_max_x = True
    limit.use_min_z = limit.use_max_z = True
    limit.min_x = limit.max_x = 0.0
    limit.min_z = limit.max_z = 0.0

    limit.use_min_y = True
    limit.use_max_y = True
    limit.min_y = CAM_POS_START[1] + (FOCAL_START_MM - FOCAL_MAX_MM) / MM_PER_M
    limit.max_y = CAM_POS_START[1] + (FOCAL_START_MM - FOCAL_MIN_MM) / MM_PER_M

    # --- Drivers ---
    f_expr = (
        f"max(min({FOCAL_START_MM} - ((fy - py) * {MM_PER_M}), "
        f"{FOCAL_MAX_MM}), {FOCAL_MIN_MM})"
    )

    # Lens
    lens_drv = cam.data.driver_add("lens").driver

    v1 = lens_drv.variables.new()
    v1.name = "fy"
    v1.type = 'TRANSFORMS'
    v1.targets[0].id = focal
    v1.targets[0].transform_type = 'LOC_Y'
    v1.targets[0].transform_space = 'WORLD_SPACE'

    v2 = lens_drv.variables.new()
    v2.name = "py"
    v2.type = 'TRANSFORMS'
    v2.targets[0].id = cam_pos
    v2.targets[0].transform_type = 'LOC_Y'
    v2.targets[0].transform_space = 'WORLD_SPACE'

    lens_drv.expression = f_expr

    # Compensation
    comp_drv = cam_focal.driver_add("location", 2).driver

    v3 = comp_drv.variables.new()
    v3.name = "fy"
    v3.type = 'TRANSFORMS'
    v3.targets[0].id = focal
    v3.targets[0].transform_type = 'LOC_Y'
    v3.targets[0].transform_space = 'WORLD_SPACE'

    v4 = comp_drv.variables.new()
    v4.name = "py"
    v4.type = 'TRANSFORMS'
    v4.targets[0].id = cam_pos
    v4.targets[0].transform_type = 'LOC_Y'
    v4.targets[0].transform_space = 'WORLD_SPACE'

    v5 = comp_drv.variables.new()
    v5.name = "d0"
    v5.type = 'LOC_DIFF'
    v5.targets[0].id = cam_aim
    v5.targets[1].id = cam_target

    comp_drv.expression = f"d0 * (({f_expr} / {FOCAL_START_MM}) - 1)"