#!/usr/bin/env python
# coding: utf-8

# In[ ]:





# In[10]:


import rasterio

# ✅ Safer path format (forward slashes)
tiff_path = "D:/Assignment2/S1_Sigma0_VV_2017.tif"

try:
    with rasterio.open(tiff_path) as src:
        print("✅ File opened successfully!")
        print("\n--- File Information ---")
        print(f"Driver: {src.driver}")
        print(f"Width: {src.width}")
        print(f"Height: {src.height}")
        print(f"Band Count: {src.count}")
        print(f"CRS: {src.crs}")
        print(f"Transform:\n{src.transform}")

        # Read first band
        band1 = src.read(1)
        print("\n--- Band 1 Info ---")
        print(f"Data type: {band1.dtype}")
        print(f"Shape: {band1.shape}")
        print(f"Min value: {band1.min()}")
        print(f"Max value: {band1.max()}")

except rasterio.errors.RasterioIOError as e:
    print("❌ Rasterio could not open the file.")
    print("Error details:", e)


# In[11]:


import matplotlib.pyplot as plt
import numpy as np
import rasterio

# Re-open to read band data
tiff_path = "D:/Assignment2/S1_Sigma0_VV_2017.tif"

with rasterio.open(tiff_path) as src:
    band1 = src.read(1)

# Simple linear stretch to 2–98 percentile for better contrast
p2, p98 = np.percentile(band1[band1 > 0], (2, 98))
stretched = np.clip(band1, p2, p98)

plt.figure(figsize=(10, 10))
plt.imshow(stretched, cmap='gray')
plt.title("Sentinel-1 Sigma0_VV (Linear Stretch)")
plt.axis('off')
plt.show()


# In[16]:


import matplotlib.pyplot as plt
import numpy as np
import rasterio

# Input and output paths
tiff_path = "D:/Assignment2/S1_Sigma0_VV_2017.tif"
out_tiff = "D:/Assignment2/S1_Sigma0_VV_2017_stretched.tif"

# Read band data
with rasterio.open(tiff_path) as src:
    band1 = src.read(1)
    meta = src.meta.copy()   # Save metadata

# Compute 2–98 percentile stretch
p2, p98 = np.percentile(band1[band1 > 0], (2, 98))
stretched = np.clip(band1, p2, p98)

# Update metadata (ensure correct data type)
meta.update(dtype=rasterio.float32)

# Save as GeoTIFF
with rasterio.open(out_tiff, "w", **meta) as dst:
    dst.write(stretched.astype(rasterio.float32), 1)

print("✅ Stretched GeoTIFF saved at:", out_tiff)

# Optional: Display the stretched image
plt.figure(figsize=(10, 10))
plt.imshow(stretched, cmap='gray')
plt.title("Sentinel-1 Sigma0_VV (Linear Stretch)")
plt.axis('off')
plt.show()


# In[20]:


import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import Polygon
import json

# --------------------------
# INPUT & OUTPUT PATHS
# --------------------------
tiff_path = "D:/Assignment2/S1_Sigma0_VV_2019.tif"
stretched_tiff = "D:/Assignment2/S1_Sigma0_VV_2019_stretched.tif"
clipped_tiff = "D:/Assignment2/S1_Sigma0_VV_2019_stretched_clipped.tif"

# --------------------------
# READ TIFF & APPLY LINEAR STRETCH
# --------------------------
with rasterio.open(tiff_path) as src:
    band1 = src.read(1)
    meta = src.meta.copy()

# Percentile stretch 2–98
p2, p98 = np.percentile(band1[band1 > 0], (2, 98))
stretched = np.clip(band1, p2, p98)

# Save stretched full image
meta.update(dtype=rasterio.float32)

with rasterio.open(stretched_tiff, "w", **meta) as dst:
    dst.write(stretched.astype(rasterio.float32), 1)

print("✔ Stretched GeoTIFF saved at:", stretched_tiff)

# --------------------------
# CREATE ROI POLYGON
# --------------------------
roi_coords = [
    [80.5024, 17.0213],
    [80.4950, 16.8211],
    [80.7916, 16.8031],
    [80.8117, 17.0234],
    [80.5024, 17.0213]
]

polygon = Polygon(roi_coords)
geojson = [json.loads(json.dumps({"type": "Polygon", "coordinates": [roi_coords]}))]

# --------------------------
# CLIP USING rasterio.mask
# --------------------------
with rasterio.open(stretched_tiff) as src:
    clipped_array, clipped_transform = mask(src, geojson, crop=True)
    clipped_meta = src.meta.copy()

# Update metadata for clipped output
clipped_meta.update({
    "height": clipped_array.shape[1],
    "width": clipped_array.shape[2],
    "transform": clipped_transform
})

# Save clipped GeoTIFF
with rasterio.open(clipped_tiff, "w", **clipped_meta) as dst:
    dst.write(clipped_array)

print("✔ Clipped GeoTIFF saved at:", clipped_tiff)

# --------------------------
# OPTIONAL: SHOW CLIPPED IMAGE
# --------------------------
plt.figure(figsize=(10, 10))
plt.imshow(clipped_array[0], cmap="gray")
plt.title("Clipped Stretched Sentinel-1 Image")
plt.axis("off")
plt.show()


# In[36]:


import os
import rasterio
import glob
import numpy as np

# --------- 1️⃣ Set SAFE folder ----------
safe_folder = r"D:/Assignment2/S2A_MSIL2A_20190210T045941_N0500_R119_T44QMD_20221207T140628.SAFE"

# --------- 2️⃣ Auto-detect GRANULE folder ----------
granule_path = glob.glob(os.path.join(safe_folder, "GRANULE", "*"))[0]
print("🟢 Detected GRANULE:", granule_path)

# --------- 3️⃣ Detect R10m folder ----------
r10_path = os.path.join(granule_path, "IMG_DATA", "R10m")
print("🟢 R10m folder:", r10_path)

# --------- 4️⃣ Filter for only 4 required bands ----------
wanted_bands = ["B02", "B03", "B04", "B08"]

jp2_files = []

for wb in wanted_bands:
    jp2 = glob.glob(os.path.join(r10_path, f"*_{wb}_10m.jp2"))
    if len(jp2) > 0:
        jp2_files.append(jp2[0])

print("\nBands selected:")
for f in jp2_files:
    print("   ", f)

# --------- 5️⃣ Read and stack as 4-band GeoTIFF ----------
bands = []
profile = None

for jp2 in jp2_files:
    with rasterio.open(jp2) as src:
        if profile is None:
            profile = src.profile
        bands.append(src.read(1))  # read only band data

stacked = np.stack(bands, axis=0)

# --------- 6️⃣ Save output ----------
out_tif = os.path.join(safe_folder, "S2A_10m_Stack_2019_4band.tif")

profile.update({
    "count": 4,
    "driver": "GTiff",
    "dtype": "float32"
})

with rasterio.open(out_tif, "w", **profile) as dst:
    dst.write(stacked.astype("float32"))

print("\n✅ 4-band (Blue, Green, Red, NIR) GeoTIFF created!")
print("📌 Output:", out_tif)


# In[40]:


# -----------------------------
# 7️⃣ Clip the stacked output
# -----------------------------
from rasterio.mask import mask
from shapely.geometry import Polygon, mapping
from pyproj import Transformer

# ---- Create polygon from ROI coordinates (lat/lon) ----
roi_polygon = Polygon(roi_coords)

# ---- Get CRS of the stacked image ----
with rasterio.open(out_tif) as src:
    img_crs = src.crs

# ---- Reproject ROI from EPSG:4326 → Sentinel CRS ----
transformer = Transformer.from_crs("EPSG:4326", img_crs, always_xy=True)
roi_reproj = [transformer.transform(x, y) for x, y in roi_coords]
roi_polygon_utm = Polygon(roi_reproj)

# ---- Perform the clipping ----
with rasterio.open(out_tif) as src:
    clipped_img, clipped_transform = mask(
        src,
        [mapping(roi_polygon_utm)],
        crop=True
    )
    clipped_meta = src.meta.copy()

# ---- Update metadata for clipped raster ----
clipped_meta.update({
    "height": clipped_img.shape[1],
    "width": clipped_img.shape[2],
    "transform": clipped_transform
})

# ---- Save clipped output ----
clipped_out = os.path.join(safe_folder, "S2A_10m_Stack_2019_Clipped1.tif")

with rasterio.open(clipped_out, "w", **clipped_meta) as dst:
    dst.write(clipped_img)

print("\n✅ Clipped GeoTIFF created successfully!")
print("📌 Output:", clipped_out)


# In[43]:


import matplotlib.pyplot as plt
import rasterio

# -----------------------------
# Load clipped image
# -----------------------------
with rasterio.open(clipped_out) as src:
    clipped_img = src.read()  # shape: (bands, rows, cols)
    clipped_meta = src.meta

# -----------------------------
# Quick visualization
# -----------------------------
# If your bands are like Sentinel-2 10m: B4=Red, B3=Green, B2=Blue
# Adjust indices depending on your stack
red = clipped_img[2]   # B4
green = clipped_img[1] # B3
blue = clipped_img[0]  # B2

# Normalize for plotting
def normalize(array):
    array_min, array_max = array.min(), array.max()
    return (array - array_min) / (array_max - array_min)

rgb = np.dstack([
    normalize(red),
    normalize(green),
    normalize(blue)
])

plt.figure(figsize=(10,10))
plt.imshow(rgb)
plt.title("Clipped Image 2019 (True Color)")
plt.axis("off")
plt.show()




# In[ ]:




