import trimesh
import numpy as np
from trimesh.transformations import translation_matrix, rotation_matrix

# Body
body = trimesh.creation.box(extents=[400, 500, 120])
body.apply_scale([1, 1, 0.8])  # adjust proportions
body.apply_translation([0, 0, -60])  # lower body
body.visual.face_colors = [255, 0, 0, 255]  # red

# Hollow interior
interior = trimesh.creation.box(extents=[360, 460, 80])
interior.apply_translation([0, 0, -60])  # align with body
interior.apply_scale([1, 1, 0.8])  # adjust proportions
try:
    body = trimesh.boolean.difference([body, interior], engine="manifold")
except Exception:
    pass  # fallback if boolean operation fails

# Wheels
wheel = trimesh.creation.cylinder(radius=40, height=80, sections=32)
wheel.apply_scale([1, 1, 0.5])  # adjust thickness
wheel.apply_translation([170, 220, -120])  # front left
wheel.visual.face_colors = [0, 0, 0, 255]  # black
wheel2 = wheel.copy()
wheel2.apply_translation([-170, 220, 0])  # front right
wheel3 = wheel.copy()
wheel3.apply_translation([170, -220, 0])  # rear left
wheel4 = wheel.copy()
wheel4.apply_translation([-170, -220, 0])  # rear right

# Windows
window = trimesh.creation.box(extents=[100, 50, 20])
window.apply_translation([0, 150, 20])  # front
window.visual.face_colors = [255, 255, 255, 128]  # white transparent
window2 = window.copy()
window2.apply_translation([0, -150, 0])  # rear

# Doors
door = trimesh.creation.box(extents=[80, 20, 100])
door.apply_translation([150, 0, 0])  # front
door.visual.face_colors = [255, 0, 0, 255]  # red
door2 = door.copy()
door2.apply_translation([-150, 0, 0])  # rear

# Scene
scene = trimesh.Scene()
scene.add_geometry(body, node_name="body")
scene.add_geometry(wheel, node_name="wheel_front_left")
scene.add_geometry(wheel2, node_name="wheel_front_right")
scene.add_geometry(wheel3, node_name="wheel_rear_left")
scene.add_geometry(wheel4, node_name="wheel_rear_right")
scene.add_geometry(window, node_name="window_front")
scene.add_geometry(window2, node_name="window_rear")
scene.add_geometry(door, node_name="door_front")
scene.add_geometry(door2, node_name="door_rear")