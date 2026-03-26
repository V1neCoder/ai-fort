import trimesh
import numpy as np

# Define the dimensions of the crate
width = 60
height = 50
depth = 80

# Base
base = trimesh.creation.box(extents=[width, depth, 2])
base.visual.face_colors = [102, 75, 31, 255]  # #964B00
base.apply_translation([0, 0, 1])

# Sides
side1 = trimesh.creation.box(extents=[width, 2, height - 2])
side1.visual.face_colors = [102, 75, 31, 255]  # #964B00
side1.apply_translation([0, depth / 2 - 1, height / 2])

side2 = trimesh.creation.box(extents=[width, 2, height - 2])
side2.visual.face_colors = [102, 75, 31, 255]  # #964B00
side2.apply_translation([0, -depth / 2 + 1, height / 2])

side3 = trimesh.creation.box(extents=[2, depth, height - 2])
side3.visual.face_colors = [102, 75, 31, 255]  # #964B00
side3.apply_translation([width / 2 - 1, 0, height / 2])

side4 = trimesh.creation.box(extents=[2, depth, height - 2])
side4.visual.face_colors = [102, 75, 31, 255]  # #964B00
side4.apply_translation([-width / 2 + 1, 0, height / 2])

# Top
top = trimesh.creation.box(extents=[width, depth, 2])
top.visual.face_colors = [118, 108, 59, 255]  # #786C3B
top.apply_translation([0, 0, height - 1])

# Create the scene
scene = trimesh.Scene()
scene.add_geometry(base, node_name="base")
scene.add_geometry(side1, node_name="side1")
scene.add_geometry(side2, node_name="side2")
scene.add_geometry(side3, node_name="side3")
scene.add_geometry(side4, node_name="side4")
scene.add_geometry(top, node_name="top")