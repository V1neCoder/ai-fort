import trimesh
import numpy as np

# Create the scene
scene = trimesh.Scene()

# Main building (hollow box)
outer_main = trimesh.creation.box(extents=[2000, 1500, 800])
outer_main.apply_translation([0, 0, 400])
inner_main = trimesh.creation.box(extents=[1800, 1300, 700])
inner_main.apply_translation([0, 0, 350])
try:
    main_building = trimesh.boolean.difference([outer_main, inner_main], engine="manifold")
except Exception:
    main_building = outer_main  # fallback if boolean fails
main_building.visual.face_colors = [255, 255, 255, 255]  # White
scene.add_geometry(main_building, node_name="main_building")

# Garage (hollow box)
outer_garage = trimesh.creation.box(extents=[500, 300, 400])
outer_garage.apply_translation([-700, -200, 200])
inner_garage = trimesh.creation.box(extents=[450, 250, 350])
inner_garage.apply_translation([-700, -200, 150])
try:
    garage = trimesh.boolean.difference([outer_garage, inner_garage], engine="manifold")
except Exception:
    garage = outer_garage  # fallback if boolean fails
garage.visual.face_colors = [128, 128, 128, 255]  # Gray
scene.add_geometry(garage, node_name="garage")

# Garden (flat rectangle)
garden = trimesh.creation.box(extents=[1000, 500, 10])
garden.apply_translation([0, 500, 0])
garden.visual.face_colors = [0, 128, 0, 255]  # Green
scene.add_geometry(garden, node_name="garden")

# Pool (flat rectangle)
pool = trimesh.creation.box(extents=[400, 200, 10])
pool.apply_translation([300, 200, 0])
pool.visual.face_colors = [0, 0, 255, 128]  # Blue
scene.add_geometry(pool, node_name="pool")

# Fountains (small cylinders)
fountain1 = trimesh.creation.cylinder(radius=20, height=50, sections=32)
fountain1.apply_translation([0, 0, 25])
fountain1.visual.face_colors = [139, 69, 19, 255]  # Brown
scene.add_geometry(fountain1, node_name="fountain1")

fountain2 = trimesh.creation.cylinder(radius=20, height=50, sections=32)
fountain2.apply_translation([500, 0, 25])
fountain2.visual.face_colors = [139, 69, 19, 255]  # Brown
scene.add_geometry(fountain2, node_name="fountain2")

# Towers (small cylinders)
tower1 = trimesh.creation.cylinder(radius=50, height=200, sections=32)
tower1.apply_translation([-500, 0, 100])
tower1.visual.face_colors = [255, 255, 255, 255]  # White
scene.add_geometry(tower1, node_name="tower1")

tower2 = trimesh.creation.cylinder(radius=50, height=200, sections=32)
tower2.apply_translation([500, 0, 100])
tower2.visual.face_colors = [255, 255, 255, 255]  # White
scene.add_geometry(tower2, node_name="tower2")