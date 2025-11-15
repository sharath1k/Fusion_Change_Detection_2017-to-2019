#!/usr/bin/env python
# coding: utf-8

# In[8]:


import numpy as np
import rasterio
from rasterio.enums import Resampling

# ------------------------------------------------------------
# INPUT FILES
# ------------------------------------------------------------
s2_path = "D:/Assignment2/Final_S2_Clipped_2019.tif"   # B2,B3,B4,B8
s1_path = "D:/Assignment2/coregisteredsentinel1_2019.tif"
out_path = "D:/Assignment2/GS_Fusion_S1_S2_2019.tif"

# ------------------------------------------------------------
# READ SENTINEL-2 (4 bands)
# ------------------------------------------------------------
with rasterio.open(s2_path) as src_s2:
    s2 = src_s2.read().astype(np.float32)    # shape: (4, H, W)
    s2_meta = src_s2.meta.copy()

B2, B3, B4, B8 = s2  # unpack

# ------------------------------------------------------------
# READ SENTINEL-1 (GRD)
# ------------------------------------------------------------
with rasterio.open(s1_path) as src_s1:

    # Ensure S1 matches S2 size/grid (resample if different)
    if (src_s1.width != s2_meta['width']) or (src_s1.height != s2_meta['height']):
        # Resample SAR to S2 grid
        print("Resampling S1 to match S2 resolution...")
        s1 = src_s1.read(
            out_shape=(1, s2_meta['height'], s2_meta['width']),
            resampling=Resampling.bilinear
        )[0].astype(np.float32)
    else:
        s1 = src_s1.read(1).astype(np.float32)

# ------------------------------------------------------------
# STEP 1 — CREATE SYNTHETIC PAN
# ------------------------------------------------------------
# Equal weight example (you can modify weights)
PAN = 0.25 * (B2 + B3 + B4 + B8)

# ------------------------------------------------------------
# STEP 2 — GRAM–SCHMIDT ORTHOGONALIZATION
# ------------------------------------------------------------

# Function for GS orthogonalization
def gram_schmidt(bands):
    U = []
    for i in range(len(bands)):
        vec = bands[i].copy()

        for j in range(i):
            proj = (np.sum(vec * U[j]) / np.sum(U[j] * U[j])) * U[j]
            vec = vec - proj

        U.append(vec)

    return np.array(U)

# Stack PAN + MS bands
stacked = np.array([PAN, B2, B3, B4, B8])

GS = gram_schmidt(stacked)  # GS[0] = GS1

# ------------------------------------------------------------
# STEP 3 — REPLACE GS1 WITH S1 SAR
# ------------------------------------------------------------
GS[0] = s1

# ------------------------------------------------------------
# STEP 4 — INVERSE GRAM–SCHMIDT (RECONSTRUCTION)
# ------------------------------------------------------------

def inverse_gs(U, original):
    """
    Reconstruct original bands from GS-orthogonalized vectors
    """
    rec = np.zeros_like(original)
    for i in range(len(U)):
        vec = U[i]
        for j in range(i):
            proj = (np.sum(original[i] * rec[j]) / np.sum(rec[j] * rec[j])) * rec[j]
            vec = vec + proj
        rec[i] = vec
    return rec

recon = inverse_gs(GS, stacked)  # gives: PAN', B2', B3', B4', B8'

# Extract reconstructed MS bands
B2_fused = recon[1]
B3_fused = recon[2]
B4_fused = recon[3]
B8_fused = recon[4]

# ------------------------------------------------------------
# SAVE FUSED OUTPUT
# ------------------------------------------------------------
s2_meta.update({
    "count": 4,
    "dtype": "float32"
})

with rasterio.open(out_path, "w", **s2_meta) as dst:
    dst.write(B2_fused.astype(np.float32), 1)
    dst.write(B3_fused.astype(np.float32), 2)
    dst.write(B4_fused.astype(np.float32), 3)
    dst.write(B8_fused.astype(np.float32), 4)

print("✅ GS Fusion Completed!")
print("Saved at:", out_path)


# In[49]:


import matplotlib.pyplot as plt
import rasterio
import numpy as np

fused_path = "D:/Assignment2/GS_Fusion_S1_S2_2017.tif"

with rasterio.open(fused_path) as src:
    B2 = src.read(1)
    B3 = src.read(2)
    B4 = src.read(3)

# Normalize for display
def norm(band):
    return (band - np.nanmin(band)) / (np.nanmax(band) - np.nanmin(band))

rgb = np.dstack((norm(B4), norm(B3), norm(B2)))   # RGB = 4-3-2

plt.figure(figsize=(10,10))
plt.imshow(rgb)
plt.title("Fused Image 2017")
plt.axis('off')
plt.show()


# In[50]:


import matplotlib.pyplot as plt
import rasterio
import numpy as np

fused_path = "D:/Assignment2/GS_Fusion_S1_S2_2019.tif"

with rasterio.open(fused_path) as src:
    B2 = src.read(1)
    B3 = src.read(2)
    B4 = src.read(3)

# Normalize for display
def norm(band):
    return (band - np.nanmin(band)) / (np.nanmax(band) - np.nanmin(band))

rgb = np.dstack((norm(B4), norm(B3), norm(B2)))   # RGB = 4-3-2

plt.figure(figsize=(10,10))
plt.imshow(rgb)
plt.title("Fused Image 2019")
plt.axis('off')
plt.show()


# In[41]:


import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# -----------------------------
# Paths
# -----------------------------
pre_path = "D:/Assignment2/GS_Fusion_S1_S2_2017.tif"
post_path = "D:/Assignment2/GS_Fusion_S1_S2_2019.tif"
out_pre_class = "D:/Assignment2/pre_class_same_colors1.tif"
out_post_class = "D:/Assignment2/post_class_same_colors1.tif"
out_change_map = "D:/Assignment2/change_map_clean.tif"

# -----------------------------
# Read images
# -----------------------------
with rasterio.open(pre_path) as src_pre:
    pre = src_pre.read().astype(np.float32)
    meta = src_pre.meta.copy()

with rasterio.open(post_path) as src_post:
    post = src_post.read().astype(np.float32)

# -----------------------------
# Align post to pre
# -----------------------------
post_aligned = np.zeros_like(pre)
for b in range(pre.shape[0]):
    reproject(
        source=post[b],
        destination=post_aligned[b],
        src_transform=src_post.transform,
        src_crs=src_post.crs,
        dst_transform=src_pre.transform,
        dst_crs=src_pre.crs,
        resampling=Resampling.bilinear
    )

# -----------------------------
# Remove null/edge pixels (NaN or very low values)
# -----------------------------
pre_mask = np.all(pre != 0, axis=0)
post_mask = np.all(post_aligned != 0, axis=0)
valid_mask = pre_mask & post_mask  # pixels valid in both

# Set invalid pixels to 0 (or ignore in clustering)
pre_flat = pre[:, valid_mask].T  # shape: (pixels, bands)
post_flat = post_aligned[:, valid_mask].T

# -----------------------------
# K-Means clustering using both pre+post together
# to ensure same cluster/color mapping
# -----------------------------
combined_flat = np.vstack([pre_flat, post_flat])
n_clusters = 5
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
kmeans.fit(combined_flat)

# Assign labels back
pre_labels = np.zeros((pre.shape[1]*pre.shape[2],), dtype=np.uint8)
post_labels = np.zeros((pre.shape[1]*pre.shape[2],), dtype=np.uint8)

pre_labels[valid_mask.flatten()] = kmeans.labels_[:pre_flat.shape[0]]
post_labels[valid_mask.flatten()] = kmeans.labels_[pre_flat.shape[0]:]

pre_class_map = pre_labels.reshape(pre.shape[1], pre.shape[2])
post_class_map = post_labels.reshape(pre.shape[1], pre.shape[2])

# -----------------------------
# Change detection
# -----------------------------
change_map = ((pre_class_map != post_class_map) & valid_mask).astype(np.uint8)

# -----------------------------
# Save maps
# -----------------------------
meta.update({"count": 1, "dtype": "uint8"})
with rasterio.open(out_pre_class, "w", **meta) as dst:
    dst.write(pre_class_map, 1)

with rasterio.open(out_post_class, "w", **meta) as dst:
    dst.write(post_class_map, 1)

with rasterio.open(out_change_map, "w", **meta) as dst:
    dst.write(change_map, 1)

print("✅ Pre/Post classified maps and change map saved.")

# -----------------------------
# Visualization with same color map
# -----------------------------
cmap = plt.get_cmap('tab10', n_clusters)
plt.figure(figsize=(18,6))

plt.subplot(1,3,1)
plt.imshow(pre_class_map, cmap=cmap, vmin=0, vmax=n_clusters-1)
plt.title("Pre Image Classification")
plt.axis('off')

plt.subplot(1,3,2)
plt.imshow(post_class_map, cmap=cmap, vmin=0, vmax=n_clusters-1)
plt.title("Post Image Classification")
plt.axis('off')

plt.subplot(1,3,3)
plt.imshow(change_map, cmap='gray')
plt.title("Change Detection Map")
plt.axis('off')

plt.show()


# In[42]:


import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# -----------------------------
# Mask invalid pixels (NaN or zeros)
# -----------------------------
valid_mask = ~np.isnan(pre_class_map)
pre_class_map_masked  = np.where(valid_mask, pre_class_map, -1)  # set invalid to -1
post_class_map_masked = np.where(valid_mask, post_class_map, -1)
change_map_masked     = np.where(valid_mask, change_map, 0)

# -----------------------------
# Define colors and labels
# -----------------------------
# Define class labels
class_labels = {
    0: "Barren Land",
    1: "Agriculture",
    2: "Forest",
    3: "Tree",
    4: "Urban"
}

# Get number of clusters
n_clusters = len(np.unique(pre_class_map[~np.isnan(pre_class_map)]))

# Assign colors for clusters
colors = plt.get_cmap('tab10', n_clusters).colors

# Create patches with proper labels
patches = [mpatches.Patch(color=colors[i], label=class_labels.get(i, f"Class {i}")) 
           for i in range(n_clusters)]

# -----------------------------
# Plot
# -----------------------------
plt.figure(figsize=(22,6))

plt.subplot(1,3,1)
plt.imshow(pre_class_map_masked, cmap='tab10', vmin=0, vmax=n_clusters-1)
plt.title("Pre Image Classification", fontsize=14, fontweight='bold')
plt.axis('off')
plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)

plt.subplot(1,3,2)
plt.imshow(post_class_map_masked, cmap='tab10', vmin=0, vmax=n_clusters-1)
plt.title("Post Image Classification", fontsize=14, fontweight='bold')
plt.axis('off')
plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)

plt.subplot(1,3,3)
plt.imshow(change_map_masked, cmap='gray')
plt.title("Change Detection Map", fontsize=14, fontweight='bold')
plt.axis('off')

plt.tight_layout()
plt.show()


# In[45]:


import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# -----------------------------
# Mask invalid pixels (NaN or zeros)
# -----------------------------
valid_mask = ~np.isnan(pre_class_map)
pre_class_map_masked  = np.where(valid_mask, pre_class_map, -1)  # set invalid to -1
post_class_map_masked = np.where(valid_mask, post_class_map, -1)
change_map_masked     = np.where(valid_mask, change_map, 0)

# -----------------------------
# Define colors and labels
# -----------------------------
# Define class labels
class_labels = {
    0: "Barren Land",
    1: "Agriculture",
    2: "Forest",
    3: "Tree",
    4: "Urban"
}

# Get number of clusters
n_clusters = len(np.unique(pre_class_map[~np.isnan(pre_class_map)]))

# Assign colors for clusters
colors = plt.get_cmap('tab10', n_clusters).colors

# Create patches with proper labels
patches = [mpatches.Patch(color=colors[i], label=class_labels.get(i, f"Class {i}")) 
           for i in range(n_clusters)]

# -----------------------------
# Plot with high DPI
# -----------------------------
plt.figure(figsize=(22,6), dpi=300)  # Increased DPI to 300

plt.subplot(1,3,1)
plt.imshow(pre_class_map_masked, cmap='tab10', vmin=0, vmax=n_clusters-1)
plt.title("Pre Image Classification", fontsize=14, fontweight='bold')
plt.axis('off')
plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)

plt.subplot(1,3,2)
plt.imshow(post_class_map_masked, cmap='tab10', vmin=0, vmax=n_clusters-1)
plt.title("Post Image Classification", fontsize=14, fontweight='bold')
plt.axis('off')
plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)

plt.subplot(1,3,3)
plt.imshow(change_map_masked, cmap='gray')
plt.title("Change Detection Map", fontsize=14, fontweight='bold')
plt.axis('off')

plt.tight_layout()
plt.show()

# Optional: Save with high DPI
plt.savefig('classification_results.png', dpi=300, bbox_inches='tight')


# In[ ]:




