import trimesh
import numpy as np

# Define dimensions
width = 80
height = 60
depth = 80
wall_thickness = 2

# Create base
base = trimesh.creation.box(extents=[width, depth, wall_thickness])
base.visual.face_colors = [160, 110, 60, 255]

# Create sides
side1 = trimesh.creation.box(extents=[width, wall_thickness, height - wall_thickness])
side1.apply_translation([0, depth/2 - wall_thickness/2, height/2 - wall_thickness/2])
side1.visual.face_colors = [160, 110, 60, 255]

side2 = trimesh.creation.box(extents=[depth, wall_thickness, height - wall_thickness])
side2.apply_translation([width/2 - wall_thickness/2, 0, height/2 - wall_thickness/2])
side2.visual.face_colors = [160, 110, 60, 255]

side3 = trimesh.creation.box(extents=[width, wall_thickness, height - wall_thickness])
side3.apply_translation([0, -depth/2 + wall_thickness/2, height/2 - wall_thickness/2])
side3.visual.face_colors = [160, 110, 60, 255]

side4 = trimesh.creation.box(extents=[depth, wall_thickness, height - wall_thickness])
side4.apply_translation([-width/2 + wall_thickness/2, 0, height/2 - wall_thickness/2])
side4.visual.face_colors = [160, 110, 60, 255]

# Create top
top = trimesh.creation.box(extents=[width, depth, wall_thickness])
top.apply_translation([0, 0, height - wall_thickness/2])
top.visual.face_colors = [160, 110, 60, 255]

# Create scene
scene = trimesh.Scene()

# Add components to scene
scene.add_geometry(base, node_name="base")
scene.add_geometry(side1, node_name="side1")
scene.add_geometry(side2, node_name="side2")
scene.add_geometry(side3, node_name="side3")
scene.add_geometry(side4, node_name="side4")
scene.add_geometry(top, node_name="top")