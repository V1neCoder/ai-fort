"""Trimesh API reference injected into AI code generation prompts."""

TRIMESH_API_REFERENCE = """
## trimesh Python API — Quick Reference for 3D Asset Construction

### Creating Primitives
```python
import trimesh
import numpy as np

# Box (centered at origin)
box = trimesh.creation.box(extents=[width, depth, height])

# Cylinder (centered, along Z axis)
cyl = trimesh.creation.cylinder(radius=r, height=h, sections=32)

# Cone
cone = trimesh.creation.cone(radius=r, height=h, sections=32)

# Sphere
sphere = trimesh.creation.icosphere(radius=r, subdivisions=3)

# Capsule
cap = trimesh.creation.capsule(height=h, radius=r)

# Annulus (ring/donut cross-section)
ann = trimesh.creation.annulus(r_min=inner, r_max=outer, height=h)
```

### Transformations
```python
from trimesh.transformations import translation_matrix, rotation_matrix

# Move a mesh
mesh.apply_translation([x, y, z])

# Or use a 4x4 matrix
T = translation_matrix([x, y, z])
mesh.apply_transform(T)

# Rotate (angle in radians, axis as [x,y,z])
R = rotation_matrix(angle_rad, [0, 0, 1])  # rotate around Z
mesh.apply_transform(R)

# Scale uniformly
mesh.apply_scale(factor)
```

### Coloring Meshes
```python
# Solid color for entire mesh (RGBA, 0-255)
mesh.visual.face_colors = [R, G, B, 255]

# Per-face colors (array of shape [n_faces, 4])
colors = np.full((len(mesh.faces), 4), [200, 180, 160, 255], dtype=np.uint8)
mesh.visual.face_colors = colors

# Common colors:
# Wood:   [160, 120, 80, 255]
# Stone:  [160, 160, 155, 255]
# Brick:  [180, 80, 60, 255]
# Metal:  [180, 180, 190, 255]
# Glass:  [180, 220, 255, 128]
# Grass:  [80, 140, 60, 255]
# Roof:   [120, 60, 40, 255]
# White:  [240, 240, 235, 255]
# Dark:   [50, 50, 55, 255]
```

### Building Scenes (Multiple Meshes)
```python
scene = trimesh.Scene()

# Add meshes with names
scene.add_geometry(wall_mesh, node_name="walls")
scene.add_geometry(roof_mesh, node_name="roof")
scene.add_geometry(door_mesh, node_name="door")

# Add with transform
scene.add_geometry(mesh, node_name="name", transform=T_matrix)
```

### Combining Meshes
```python
# Concatenate (fast, no boolean)
combined = trimesh.util.concatenate([mesh_a, mesh_b, mesh_c])

# Boolean operations (slower but precise)
result = trimesh.boolean.union([mesh_a, mesh_b], engine="manifold")
result = trimesh.boolean.difference([base, cutout], engine="manifold")
result = trimesh.boolean.intersection([mesh_a, mesh_b], engine="manifold")
```

### Extrusion (2D shape to 3D)
```python
# Extrude a polygon along Z
from shapely.geometry import Polygon

poly = Polygon([(0,0), (100,0), (100,50), (0,50)])
mesh = trimesh.creation.extrude_polygon(poly, height=80)

# Extrude along a path
mesh = trimesh.creation.sweep_polygon(poly, path_points)
```

### Creating Custom Meshes from Vertices/Faces
```python
vertices = np.array([
    [0, 0, 0],
    [100, 0, 0],
    [50, 0, 100],
    [50, 50, 50],
])
faces = np.array([
    [0, 1, 2],
    [0, 1, 3],
    [1, 2, 3],
    [0, 2, 3],
])
mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
mesh.fix_normals()
```

### Useful Patterns

#### Hollow Box (room/building)
```python
outer = trimesh.creation.box(extents=[w, d, h])
inner = trimesh.creation.box(extents=[w - wall*2, d - wall*2, h - wall*2])
inner.apply_translation([0, 0, wall])  # shift up so floor exists
hollow = trimesh.boolean.difference([outer, inner], engine="manifold")
```

#### Triangular Roof (prism)
```python
vertices = np.array([
    [-w/2, -d/2, 0], [w/2, -d/2, 0],
    [w/2, d/2, 0], [-w/2, d/2, 0],
    [0, -d/2, peak], [0, d/2, peak],
])
faces = np.array([
    [0,1,4], [1,2,5], [2,3,5], [3,0,4],  # sides
    [1,5,4], [3,4,5],                      # ridge
    [0,3,2], [0,2,1],                      # bottom
])
roof = trimesh.Trimesh(vertices=vertices, faces=faces)
roof.fix_normals()
```

#### Terrain Heightmap
```python
x = np.linspace(0, width, resolution)
y = np.linspace(0, depth, resolution)
X, Y = np.meshgrid(x, y)
Z = amplitude * np.sin(X * freq) * np.cos(Y * freq)  # or any height function

vertices = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
# Build triangle faces from grid
faces = []
for i in range(resolution - 1):
    for j in range(resolution - 1):
        v = i * resolution + j
        faces.append([v, v+1, v+resolution])
        faces.append([v+1, v+resolution+1, v+resolution])
terrain = trimesh.Trimesh(vertices=vertices, faces=np.array(faces))
terrain.visual.face_colors = [80, 140, 60, 255]  # grass green
```

### Export
```python
# The scene or mesh will be exported by the pipeline — just build it.
# Your code must define a variable called 'scene' (trimesh.Scene).
# If you have a single mesh, wrap it:
scene = trimesh.Scene()
scene.add_geometry(my_mesh, node_name="main")
```

### RULES
1. All dimensions are in CENTIMETERS
2. Your code MUST define a variable called `scene` (trimesh.Scene)
3. Use scene.add_geometry() to add named parts
4. Color every mesh — no default gray
5. Keep vertex count under 50,000 total
6. Ensure meshes are watertight when possible (call mesh.fix_normals())
7. Place the asset centered at origin, sitting on the XY plane (Z up)
8. Only import: trimesh, numpy, math — nothing else
"""

# Compact examples for specific categories
CATEGORY_EXAMPLES = {
    "furniture": """
# Example: Simple wooden chair
scene = trimesh.Scene()

# Seat
seat = trimesh.creation.box(extents=[45, 45, 5])
seat.apply_translation([0, 0, 45])
seat.visual.face_colors = [160, 120, 80, 255]
scene.add_geometry(seat, node_name="seat")

# Four legs
for dx, dy in [(-18,-18),(18,-18),(18,18),(-18,18)]:
    leg = trimesh.creation.cylinder(radius=2.5, height=45, sections=8)
    leg.apply_translation([dx, dy, 22.5])
    leg.visual.face_colors = [140, 100, 60, 255]
    scene.add_geometry(leg, node_name=f"leg_{dx}_{dy}")

# Back
back = trimesh.creation.box(extents=[45, 4, 40])
back.apply_translation([0, -20, 67.5])
back.visual.face_colors = [160, 120, 80, 255]
scene.add_geometry(back, node_name="back")
""",
    "architecture": """
# Example: Simple house with roof
scene = trimesh.Scene()

# Walls (hollow box)
outer = trimesh.creation.box(extents=[600, 500, 280])
outer.apply_translation([0, 0, 140])
inner = trimesh.creation.box(extents=[580, 480, 270])
inner.apply_translation([0, 0, 145])
try:
    walls = trimesh.boolean.difference([outer, inner], engine="manifold")
except Exception:
    walls = outer  # fallback if boolean fails
walls.visual.face_colors = [220, 210, 195, 255]
scene.add_geometry(walls, node_name="walls")

# Roof (triangular prism)
hw, hd, peak = 320, 270, 180
verts = np.array([
    [-hw,-hd,280], [hw,-hd,280], [hw,hd,280], [-hw,hd,280],
    [0,-hd,280+peak], [0,hd,280+peak],
])
faces = np.array([
    [0,1,4],[1,2,5],[2,3,5],[3,0,4],
    [1,5,4],[3,4,5],[0,3,2],[0,2,1],
])
roof = trimesh.Trimesh(vertices=verts, faces=faces)
roof.fix_normals()
roof.visual.face_colors = [140, 70, 40, 255]
scene.add_geometry(roof, node_name="roof")

# Door
door = trimesh.creation.box(extents=[80, 10, 200])
door.apply_translation([0, -250, 100])
door.visual.face_colors = [100, 70, 40, 255]
scene.add_geometry(door, node_name="door")
""",
    "terrain": """
# Example: Rolling terrain hill
scene = trimesh.Scene()

res = 40
width, depth = 2000, 2000
x = np.linspace(-width/2, width/2, res)
y = np.linspace(-depth/2, depth/2, res)
X, Y = np.meshgrid(x, y)

# Smooth hill using gaussian
Z = 300 * np.exp(-((X/500)**2 + (Y/500)**2))

verts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
faces = []
for i in range(res-1):
    for j in range(res-1):
        v = i*res + j
        faces.append([v, v+1, v+res])
        faces.append([v+1, v+res+1, v+res])

terrain = trimesh.Trimesh(vertices=verts, faces=np.array(faces))
terrain.fix_normals()
terrain.visual.face_colors = [80, 140, 60, 255]
scene.add_geometry(terrain, node_name="terrain")
""",
    "prop": """
# Example: Wooden barrel
scene = trimesh.Scene()

# Body
body = trimesh.creation.cylinder(radius=30, height=90, sections=16)
body.apply_translation([0, 0, 45])
body.visual.face_colors = [160, 110, 60, 255]
scene.add_geometry(body, node_name="body")

# Metal bands
for z in [15, 45, 75]:
    band = trimesh.creation.annulus(r_min=30, r_max=32, height=4)
    band.apply_translation([0, 0, z])
    band.visual.face_colors = [120, 120, 130, 255]
    scene.add_geometry(band, node_name=f"band_{z}")

# Lid
lid = trimesh.creation.cylinder(radius=30, height=3, sections=16)
lid.apply_translation([0, 0, 91.5])
lid.visual.face_colors = [150, 100, 50, 255]
scene.add_geometry(lid, node_name="lid")
""",
}
