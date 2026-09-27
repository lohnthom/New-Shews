"""Rebuild selected editable splines without applying object modifiers."""

import bpy
import numpy as np
from bpy.props import EnumProperty, IntProperty


def _values(rna):
    """Snapshot writable scalar/array properties, not RNA references."""
    result = {}
    for prop in rna.bl_rna.properties:
        if prop.is_readonly or prop.type not in {'BOOLEAN', 'INT', 'FLOAT', 'ENUM'}:
            continue
        value = getattr(rna, prop.identifier)
        result[prop.identifier] = tuple(value) if getattr(prop, 'is_array', False) else value
    return result


def _snapshot(spline):
    points = spline.bezier_points if spline.type == 'BEZIER' else spline.points
    return {'settings': _values(spline), 'points': [_values(p) for p in points]}


def _selected(record):
    return not record['settings']['hide'] and any(
        not p['hide'] and any(p.get(key, False) for key in
                             ('select', 'select_control_point', 'select_left_handle', 'select_right_handle'))
        for p in record['points']
    )


def _append_spline(curve, record):
    settings = record['settings']
    spline = curve.splines.new(settings['type'])
    points = spline.bezier_points if spline.type == 'BEZIER' else spline.points
    points.add(len(record['points']) - 1)
    for name, value in settings.items():
        # Some RNA defaults lie outside their setters' clamped range (e.g.
        # soft-body weight 0). Leave identical defaults untouched.
        if name != 'type' and getattr(spline, name) != value:
            setattr(spline, name, value)
    for point, values in zip(points, record['points']):
        # Set coordinates before asking Blender to calculate automatic handles.
        if spline.type == 'BEZIER':
            point.handle_left_type = point.handle_right_type = 'FREE'
        for name, value in values.items():
            if name not in {'handle_left_type', 'handle_right_type'} and getattr(point, name) != value:
                setattr(point, name, value)
        if spline.type == 'BEZIER':
            point.handle_left_type = values['handle_left_type']
            point.handle_right_type = values['handle_right_type']
    return spline


def _sample_centerline(context, record, count):
    """Let Blender evaluate all source knot/weight/handle configurations.

    Only a temporary, unbeveled copy is evaluated. The user's curve object,
    Geometry Nodes, other modifiers, materials and transforms are not converted.
    """
    curve = bpy.data.curves.new('NewShews_RebuildSample', 'CURVE')
    obj = None
    evaluated = None
    try:
        curve.dimensions = '3D'
        spline = _append_spline(curve, record)
        spline.hide = False
        spline.resolution_u = min(256, max(32, count * 8 // max(1, len(record['points']) - 1)))
        obj = bpy.data.objects.new('NewShews_RebuildSample', curve)
        context.scene.collection.objects.link(obj)
        context.view_layer.update()
        evaluated = obj.evaluated_get(context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        if mesh is None or len(mesh.vertices) < 2:
            raise ValueError('A selected spline cannot be evaluated; check its point count and NURBS order')
        neighbors = [[] for _ in mesh.vertices]
        for edge in mesh.edges:
            a, b = edge.vertices
            neighbors[a].append(b)
            neighbors[b].append(a)
        if any(len(n) not in {1, 2} for n in neighbors):
            raise ValueError('A selected spline is not a single curve path')
        ends = [i for i, n in enumerate(neighbors) if len(n) == 1]
        current = min(ends) if ends else 0
        visited = set()
        ordered = []
        while current not in visited:
            visited.add(current)
            ordered.append(tuple(mesh.vertices[current].co))
            following = [i for i in neighbors[current] if i not in visited]
            if not following:
                break
            current = min(following)
        if len(visited) != len(mesh.vertices):
            raise ValueError('A selected spline contains disconnected geometry')
        if record['settings']['use_cyclic_u']:
            ordered.append(ordered[0])
        return np.asarray(ordered, dtype=float)
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.curves.remove(curve)


def _resample(samples, fractions, transform):
    # Use world-space distances so nonuniform object scale does not bunch points.
    lengths = np.linalg.norm(np.diff(samples, axis=0) @ transform.T, axis=1)
    distances = np.r_[0.0, np.cumsum(lengths)]
    if not np.isfinite(distances[-1]) or distances[-1] <= 1e-12:
        raise ValueError('Cannot rebuild a zero-length spline')
    keep = np.r_[True, np.diff(distances) > 0.0]
    distances = distances[keep] / distances[-1]
    samples = samples[keep]
    return np.column_stack([np.interp(fractions, distances, samples[:, axis]) for axis in range(3)])


def _basis(count, degree, parameters, cyclic):
    """B-spline basis for Blender's uniform or endpoint knot modes."""
    if cyclic:
        knots = np.arange(count + 2 * degree + 1, dtype=float)
        u = degree + np.asarray(parameters) * count
    else:
        knots = np.r_[np.zeros(degree + 1),
                      np.arange(1, count - degree) / (count - degree),
                      np.ones(degree + 1)]
        u = np.asarray(parameters)
    basis = ((u[:, None] >= knots[:-1]) & (u[:, None] < knots[1:])).astype(float)
    for order in range(1, degree + 1):
        width = len(knots) - order - 1
        left_den = knots[order:order + width] - knots[:width]
        right_den = knots[order + 1:order + width + 1] - knots[1:width + 1]
        left = np.divide(u[:, None] - knots[:width], left_den,
                         out=np.zeros((len(u), width)), where=left_den != 0)
        right = np.divide(knots[order + 1:order + width + 1] - u[:, None], right_den,
                          out=np.zeros((len(u), width)), where=right_den != 0)
        basis = left * basis[:, :width] + right * basis[:, 1:width + 1]
    if cyclic:
        folded = basis[:, :count].copy()
        for i in range(count, basis.shape[1]):
            folded[:, i % count] += basis[:, i]
        return folded
    basis[u == 1.0, -1] = 1.0
    return basis


def _fit_nurbs(samples, count, cyclic, transform):
    degree = min(3, count - 1)
    parameters = np.linspace(0.0, 1.0, max(128, count * 4), endpoint=not cyclic)
    targets = _resample(samples, parameters, transform)
    basis = _basis(count, degree, parameters, cyclic)
    if cyclic:
        controls = np.linalg.lstsq(basis, targets, rcond=None)[0]
    else:
        controls = np.empty((count, 3))
        controls[0], controls[-1] = targets[0], targets[-1]
        if count > 2:
            residual = targets - basis[:, :1] * controls[0] - basis[:, -1:] * controls[-1]
            controls[1:-1] = np.linalg.lstsq(basis[:, 1:-1], residual, rcond=None)[0]
    if not np.isfinite(controls).all():
        raise ValueError('Could not fit the selected spline')
    return controls


def _rebuild_record(context, obj, record, count, curve_type):
    cyclic = record['settings']['use_cyclic_u']
    if len(record['points']) < 2:
        raise ValueError('Selected splines need at least two source points')
    if cyclic and count < 3:
        raise ValueError('Closed splines need at least three rebuilt points')
    samples = _sample_centerline(context, record, count)
    transform = np.asarray(obj.matrix_world.to_3x3(), dtype=float)
    fractions = np.linspace(0.0, 1.0, count, endpoint=not cyclic)
    coords = (_fit_nurbs(samples, count, cyclic, transform) if curve_type == 'NURBS'
              else _resample(samples, fractions, transform))
    settings = dict(record['settings'], type=curve_type, order_u=min(4, count),
                    use_endpoint_u=not cyclic, use_bezier_u=False, hide=False)
    # Radius/tilt are resampled over the source control-point sequence. Geometry
    # fitting is independent; these profiles are approximate after a rebuild.
    source = record['points']
    source_t = np.linspace(0.0, 1.0, len(source), endpoint=not cyclic)
    if cyclic:
        source = source + source[:1]
        source_t = np.r_[source_t, 1.0]
    radii = np.interp(fractions, source_t, [p['radius'] for p in source])
    tilts = np.interp(fractions, source_t, [p['tilt'] for p in source])
    points = []
    for co, radius, tilt in zip(coords, radii, tilts):
        point = {'radius': float(radius), 'tilt': float(tilt), 'hide': False}
        if curve_type == 'BEZIER':
            point.update(co=tuple(co), handle_left=tuple(co), handle_right=tuple(co),
                         handle_left_type='AUTO', handle_right_type='AUTO',
                         select_control_point=True, select_left_handle=True, select_right_handle=True)
        else:
            point.update(co=(*co, 1.0), select=True)
        points.append(point)
    return {'settings': settings, 'points': points}


class STUDIO_OT_curve_rebuild(bpy.types.Operator):
    bl_idname = 'studio.curve_rebuild'
    bl_label = 'Rebuild Curve'
    bl_description = 'Rebuild each selected spline with an exact number of editable control points'
    bl_options = {'REGISTER', 'UNDO'}

    point_count: IntProperty(name='Point Count', description='Control points per selected spline',
                             default=12, min=2, max=512)
    curve_type: EnumProperty(name='Curve Type', default='NURBS', items=(
        ('NURBS', 'NURBS', 'Fit a smooth NURBS curve (up to cubic order)'),
        ('BEZIER', 'Bézier', 'Evenly spaced anchors with automatic handles'),
        ('POLY', 'Poly', 'Evenly spaced points connected by straight segments'),
    ))

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_CURVE' and context.edit_object is not None
                and context.edit_object.type == 'CURVE')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'point_count')
        layout.prop(self, 'curve_type')
        layout.label(text='Rebuilds whole splines with selected points.')
        layout.label(text='Fewer points can change the shape.', icon='INFO')

    def execute(self, context):
        plans = []
        total = 0
        try:
            # Flush current Edit Mode coordinates/selection before reading RNA.
            for obj in context.objects_in_mode_unique_data:
                if obj.type != 'CURVE':
                    continue
                obj.update_from_editmode()
                original = [_snapshot(s) for s in obj.data.splines]
                selected = [i for i, record in enumerate(original) if _selected(record)]
                if not selected:
                    continue
                if obj.data.shape_keys:
                    raise ValueError('Curves with shape keys cannot be rebuilt; remove the shape keys first')
                if obj.data.animation_data:
                    raise ValueError('Animated curve data cannot be rebuilt safely; use an unanimated copy')
                rebuilt = list(original)
                for i in selected:
                    rebuilt[i] = _rebuild_record(context, obj, original[i], self.point_count, self.curve_type)
                active = next((i for i, s in enumerate(obj.data.splines) if s == obj.data.splines.active), None)
                plans.append((obj.data, original, rebuilt, active))
                total += len(selected)
            if not plans:
                raise ValueError('Select at least one control point on a spline to rebuild')
        except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}

        def write(curve, records, active):
            curve.splines.clear()
            for record in records:
                _append_spline(curve, record)
            if active is not None:
                curve.splines.active = curve.splines[active]

        # Only commit once every selected spline has been successfully fitted.
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            for curve, original, rebuilt, active in plans:
                write(curve, rebuilt, active)
        except Exception as exc:
            for curve, original, rebuilt, active in plans:
                write(curve, original, active)
            self.report({'ERROR'}, f'Curve rebuild failed: {exc}')
            return {'CANCELLED'}
        finally:
            bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, f'Rebuilt {total} spline(s): {self.point_count} points each, {self.curve_type}')
        return {'FINISHED'}


classes = (STUDIO_OT_curve_rebuild,)
