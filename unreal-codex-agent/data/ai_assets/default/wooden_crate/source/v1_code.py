import trimesh
import numpy as np

# Create the scene
scene = trimesh.Scene()

# Base
base = trimesh.creation.box(extents=[80, 80, 5])
base.visual.face_colors = [150, 100, 50, 255]  # #964B00
scene.add_geometry(base, node_name="base")

# Sides
sides = []
for i in range(4):
    side = trimesh.creation.box(extents=[80, 5, 60])
    if i == 0:
        side.apply_translation([0, 0, 5])
    elif i == 1:
        side.apply_translation([80, 0, 5])
        side.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0, 0, 1]))
    elif i == 2:
        side.apply_translation([0, 80, 5])
    elif i == 3:
        side.apply_translation([-80, 0, 5])
        side.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0, 0, 1]))
    side.visual.face_colors = [100, 75, 30, 255]  # #663300
    scene.add_geometry(side, node_name=f"side_{i}")

# Top
top = trimesh.creation.box(extents=[80, 80, 5])
top.apply_translation([0, 0, 70])
top.visual.face_colors = [70, 45, 30, 255]  # #452B1F
scene.add_geometry(top, node_name="top")