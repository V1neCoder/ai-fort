import trimesh
import numpy as np

# Create a crate
scene = trimesh.Scene()

# Base
base = trimesh.creation.box(extents=[60, 60, 5])
base.visual.face_colors = [150, 100, 50, 255]  # rustic color
scene.add_geometry(base, node_name="base")

# Sides
side1 = trimesh.creation.box(extents=[60, 5, 50])
side1.apply_translation([0, 30, 0])
side1.visual.face_colors = [150, 100, 50, 255]  # rustic color
scene.add_geometry(side1, node_name="side1")

side2 = trimesh.creation.box(extents=[60, 5, 50])
side2.apply_translation([0, -30, 0])
side2.visual.face_colors = [150, 100, 50, 255]  # rustic color
scene.add_geometry(side2, node_name="side2")

side3 = trimesh.creation.box(extents=[5, 60, 50])
side3.apply_translation([30, 0, 0])
side3.visual.face_colors = [150, 100, 50, 255]  # rustic color
scene.add_geometry(side3, node_name="side3")

side4 = trimesh.creation.box(extents=[5, 60, 50])
side4.apply_translation([-30, 0, 0])
side4.visual.face_colors = [150, 100, 50, 255]  # rustic color
scene.add_geometry(side4, node_name="side4")

# Top
top = trimesh.creation.box(extents=[60, 60, 5])
top.apply_translation([0, 0, 55])
top.visual.face_colors = [150, 100, 50, 255]  # rustic color
scene.add_geometry(top, node_name="top")