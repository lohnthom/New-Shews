"""Run with blender --background --factory-startup --python-exit-code 1 --python this_file."""
import importlib.util
from pathlib import Path
import sys
import unittest

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('newshews', ROOT / '__init__.py',
                                            submodule_search_locations=[str(ROOT)])
addon = importlib.util.module_from_spec(spec)
sys.modules['newshews'] = addon
spec.loader.exec_module(addon)
addon.register()
from newshews.tools import curve_rebuild as rebuild


class CurveRebuildTests(unittest.TestCase):
    maxDiff = None
    def setUp(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

    def curve(self, kind='NURBS', cyclic=False, offset=0):
        data = bpy.data.curves.new('Test', 'CURVE')
        data.dimensions = '3D'
        obj = bpy.data.objects.new('Test', data)
        bpy.context.collection.objects.link(obj)
        spline = data.splines.new(kind)
        points = spline.bezier_points if kind == 'BEZIER' else spline.points
        points.add(5)
        for i, point in enumerate(points):
            co = (i + offset, np.sin(i), 0.2 * i)
            if kind == 'BEZIER':
                point.co = co
                point.handle_left_type = point.handle_right_type = 'AUTO'
                point.select_control_point = True
            else:
                point.co = (*co, 1)
                point.select = True
        spline.order_u = 4
        spline.use_endpoint_u = not cyclic
        spline.use_cyclic_u = cyclic
        return obj

    def edit(self, *objects):
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.object.mode_set(mode='EDIT')

    def test_all_input_and_output_types(self):
        for source in ('NURBS', 'BEZIER', 'POLY'):
            for output in ('NURBS', 'BEZIER', 'POLY'):
                with self.subTest(source=source, output=output):
                    self.setUp()
                    obj = self.curve(source)
                    self.edit(obj)
                    result = bpy.ops.studio.curve_rebuild(point_count=9, curve_type=output)
                    self.assertEqual(result, {'FINISHED'})
                    self.assertEqual(bpy.context.mode, 'EDIT_CURVE')
                    obj.update_from_editmode()
                    s = obj.data.splines[0]
                    self.assertEqual(s.type, output)
                    points = s.bezier_points if output == 'BEZIER' else s.points
                    self.assertEqual(len(points), 9)
                    np.testing.assert_allclose(points[0].co[:3], (0, 0, 0), atol=1e-4)
                    np.testing.assert_allclose(points[-1].co[:3], (5, np.sin(5), 1), atol=1e-4)

    def test_unselected_splines_and_object_settings(self):
        obj = self.curve('BEZIER')
        other = obj.data.splines.new('POLY')
        other.points.add(1)
        other.points[0].co = (7, 8, 9, 1)
        other.points[1].co = (10, 11, 12, 1)
        for p in other.points:
            p.select = False
        before = rebuild._snapshot(other)
        obj.data.bevel_depth = .02
        modifier = obj.modifiers.new('Keep modifier', 'MIRROR')
        modifier.show_viewport = False
        obj.scale = (2, 3, 4)
        self.edit(obj)
        bpy.ops.studio.curve_rebuild(point_count=7)
        obj.update_from_editmode()
        self.assertEqual(before, rebuild._snapshot(obj.data.splines[1]))
        self.assertAlmostEqual(obj.data.bevel_depth, .02)
        self.assertEqual(obj.modifiers[0], modifier)
        self.assertEqual(tuple(obj.scale), (2, 3, 4))

    def test_closed_nurbs_fit(self):
        bpy.ops.curve.primitive_nurbs_circle_add(radius=2)
        obj = bpy.context.object
        self.edit(obj)
        bpy.ops.studio.curve_rebuild(point_count=12)
        obj.update_from_editmode()
        s = obj.data.splines[0]
        self.assertTrue(s.use_cyclic_u)
        self.assertEqual(len(s.points), 12)
        samples = rebuild._sample_centerline(bpy.context, rebuild._snapshot(s), 12)
        np.testing.assert_allclose(np.linalg.norm(samples[:, :2], axis=1), 2, atol=.025)

    def test_selected_splines_across_objects(self):
        first, second = self.curve(), self.curve('POLY', offset=10)
        self.edit(first, second)
        bpy.ops.studio.curve_rebuild(point_count=5)
        for obj in (first, second):
            obj.update_from_editmode()
            self.assertEqual(len(obj.data.splines[0].points), 5)
            self.assertEqual(obj.mode, 'EDIT')

    def test_validation_does_not_change_source_or_leak_samples(self):
        obj = self.curve(cyclic=True)
        self.edit(obj)
        obj.update_from_editmode()
        before = rebuild._snapshot(obj.data.splines[0])
        self.assertEqual(bpy.ops.studio.curve_rebuild(point_count=2), {'CANCELLED'})
        obj.update_from_editmode()
        self.assertEqual(before, rebuild._snapshot(obj.data.splines[0]))
        self.assertEqual(bpy.context.mode, 'EDIT_CURVE')
        self.assertFalse(any(o.name.startswith('NewShews_RebuildSample') for o in bpy.data.objects))

    def test_no_selection_and_degenerate(self):
        obj = self.curve()
        for p in obj.data.splines[0].points:
            p.select = False
        self.edit(obj)
        self.assertEqual(bpy.ops.studio.curve_rebuild(), {'CANCELLED'})
        bpy.ops.object.mode_set(mode='OBJECT')
        for p in obj.data.splines[0].points:
            p.co = (0, 0, 0, 1)
            p.select = True
        self.edit(obj)
        counts = (len(bpy.data.objects), len(bpy.data.curves))
        self.assertEqual(bpy.ops.studio.curve_rebuild(), {'CANCELLED'})
        self.assertEqual(counts, (len(bpy.data.objects), len(bpy.data.curves)))


suite = unittest.defaultTestLoader.loadTestsFromTestCase(CurveRebuildTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise AssertionError('Curve rebuild tests failed')
addon.unregister()
