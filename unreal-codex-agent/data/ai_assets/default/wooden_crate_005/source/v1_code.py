import trimesh
import numpy as np

# Create a crate
scene = trimesh.Scene()

# Base
base = trimesh.creation.box(extents=[60, 60, 5])
base.visual.face_colors = [160, 110, 60, 255]
scene.add_geometry(base, node_name="base")

# Sides
side1 = trimesh.creation.box(extents=[5, 60, 50])
side1.apply_translation([27.5, 0, 25])
side1.visual.face_colors = [160, 110, 60, 255]
scene.add_geometry(side1, node_name="side1")

side2 = trimesh.creation.box(extents=[5, 60, 50])
side2.apply_translation([-32.5, 0, 25])
side2.visual.face_colors = [160, 110, 60, 255]
scene.add_geometry(side2, node_name="side2")

side3 = trimesh.creation.box(extents=[60, 5, 50])
side3.apply_translation([0, 27.5, 25])
side3.visual.face_colors = [160, 110, 60, 255]
scene.add_geometry(side3, node_name="side3")

side4 = trimesh.creation.box(extents=[60, 5, 50])
side4.apply_translation([0, -32.5, 25])
side4.visual.face_colors = [160, 110, 60, 255]
scene.add_geometry(side4, node_name="side4")

# Top
top = trimesh.creation.box(extents=[60, 60, 5])
top.apply_translation([0, 0, 55])
top.visual.face_colors = [150, 100, 50, 255]
scene.add_geometry(top, node_name="top")

# Add some wooden planks texture
plank1 = trimesh.creation.box(extents=[10, 60, 2])
plank1.apply_translation([20, 0, 10])
plank1.visual.face_colors = [150, 75, 0, 255]
scene.add_geometry(plank1, node_name="plank1")

plank2 = trimesh.creation.box(extents=[10, 60, 2])
plank2.apply_translation([-20, 0, 10])
plank2.visual.face_colors = [150, 75, 0, 255]
scene.add_geometry(plank2, node_name="plank2")

plank3 = trimesh.creation.box(extents=[60, 10, 2])
plank3.apply_translation([0, 20, 10])
plank3.visual.face_colors = [150, 75, 0, 255]
scene.add_geometry(plank3, node_name="plank3")

plank4 = trimesh.creation.box(extents=[60, 10, 2])
plank4.apply_translation([0, -20, 10])
plank4.visual.face_colors = [150, 75, 0, 255]
scene.add_geometry(plank4, node_name="plank4")