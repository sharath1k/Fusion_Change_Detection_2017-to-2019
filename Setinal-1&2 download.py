#!/usr/bin/env python
# coding: utf-8

# In[2]:


import folium

# --------------------------
# ROI coordinates [lat, lon] for folium
roi_coords = [
    [17.0213, 80.5024],
    [16.8211, 80.4950],
    [16.8031, 80.7916],
    [17.0234, 80.8117],
    [17.0213, 80.5024]
]

# Create a map centered on ROI
m = folium.Map(location=[17.0, 80.6], zoom_start=10)

# Add ROI polygon
folium.Polygon(
    locations=roi_coords,
    color='red',
    weight=3,
    fill=True,
    fill_opacity=0.3,
    popup="ROI"
).add_to(m)

# Add vertices as markers
for lat, lon in roi_coords:
    folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        color='blue',
        fill=True,
        fill_color='blue'
    ).add_to(m)

# Display map in Jupyter
m


# In[8]:


import requests
import json
import os
from shapely.wkt import loads as wkt_loads
from shapely.geometry import Polygon, shape
from datetime import datetime
from tqdm import tqdm

# ========= 🌐 PROXY SETTINGS (if required) =========
os.environ["http_proxy"] = "http://edcguest:edcguest@172.31.100.14:3128/"
os.environ["https_proxy"] = "http://edcguest:edcguest@172.31.100.14:3128/"

# ========= 1️⃣ AUTHENTICATION =========
def get_access_token(username, password):
    """Authenticate with Copernicus Data Space Ecosystem"""
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password"
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    print("✅ Authenticated successfully")
    return r.json()["access_token"]

# ========= 2️⃣ SEARCH SENTINEL-1 =========
def search_sentinel1(access_token, coords, start_date, end_date,
                     product_type='GRD-HD', orbit_dir=None):
    """Search Sentinel-1 products in a given area and date range"""
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    # Convert ROI to POLYGON string
    coord_str = ",".join([f"{lon} {lat}" for lon, lat in coords])
    geometry = f"POLYGON(({coord_str}))"
    print(f"Using Geometry: {geometry}")

    # Filter query (Updated for GRD-HD or VV+VH, and DESCENDING)
    filter_query = (
        f"Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{geometry}') and "
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq '{product_type}') and "
        f"ContentDate/Start ge {start_date}T00:00:00.000Z and "
        f"ContentDate/Start le {end_date}T23:59:59.999Z"
    )

    # Optional orbit direction
    if orbit_dir:
        filter_query += (
            f" and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'orbitDirection' "
            f"and att/OData.CSC.StringAttribute/Value eq '{orbit_dir}')"
        )

    params = {
        "$filter": filter_query,
        "$orderby": "ContentDate/Start asc",
        "$top": 100,
        "$select": "Id,Name,ContentDate,GeoFootprint"
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()

    # Debugging: Print the full API response to inspect
    response = r.json()
    print(json.dumps(response, indent=2))

    return response.get("value", [])

# ========= 3️⃣ PARSE FOOTPRINT =========
def parse_footprint(fp):
    if isinstance(fp, str):
        return wkt_loads(fp)
    elif isinstance(fp, dict):
        return shape(fp)
    else:
        raise ValueError("Unknown footprint format")

# ========= 4️⃣ GET INTERSECTING PRODUCTS =========
def get_intersecting_products(products, roi_polygon):
    """Return products whose footprints intersect the ROI"""
    intersecting = []
    for prod in products:
        try:
            footprint = parse_footprint(prod["GeoFootprint"])
            if footprint.intersects(roi_polygon):
                intersecting.append(prod)
        except Exception as e:
            print(f"⚠️ Error checking {prod.get('Name','unknown')}: {e}")
    return intersecting

# ========= 5️⃣ DOWNLOAD PRODUCT =========
def download_product(username, password, product_id, product_name, output_folder="S1_downloads"):
    """Download Sentinel-1 product with progress bar and fresh token"""
    os.makedirs(output_folder, exist_ok=True)

    # Get fresh token
    print("🔄 Getting fresh access token for download...")
    fresh_token = get_access_token(username, password)

    url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    headers = {"Authorization": f"Bearer {fresh_token}"}
    output_path = os.path.join(output_folder, f"{product_name}.zip")

    print(f"\n📥 Downloading: {product_name}")
    print(f"💾 Saving to: {output_path}")

    session = requests.Session()
    session.headers.update(headers)

    try:
        with session.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            print(f"📦 File size: {total_size / (1024**3):.2f} GB")

            chunk_size = 1024 * 1024  # 1 MB
            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True,
                         unit_divisor=1024, desc="Downloading") as pbar:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            print(f"✅ Download complete: {output_path}")
            return output_path
    except requests.exceptions.RequestException as e:
        print(f"❌ Download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

# ========= 6️⃣ MAIN EXECUTION =========
if __name__ == "__main__":
    USERNAME = "kskc.iirs@gmail.com"
    PASSWORD = "Sharath1141@@"

    # Example ROI (update with your coordinates)
    roi_coords = [
        [80.5024, 17.0213],
        [80.495, 16.8211],
        [80.7916, 16.8031],
        [80.8117, 17.0234],
        [80.5024, 17.0213]
    ]

    START_DATE = "2017-01-01"  # Wider date range
    END_DATE = "2017-02-28"
    ORBIT_DIR = "DESCENDING"  # Try with DESCENDING or None

    print("🔐 Authenticating...")
    token = get_access_token(USERNAME, PASSWORD)

    print("\n🔍 Searching Sentinel-1 GRD-HD scenes...")
    products_s1 = search_sentinel1(token, roi_coords, START_DATE, END_DATE, product_type='GRD-HD', orbit_dir=ORBIT_DIR)
    print(f"🛰 Total Sentinel-1 scenes found: {len(products_s1)}")

    roi_poly = Polygon(roi_coords)
    intersecting = get_intersecting_products(products_s1, roi_poly)
    print(f"✅ Intersecting Sentinel-1 scenes: {len(intersecting)}")

    if intersecting:
        selected = intersecting[0]
        print(f"\n🎯 Selected Sentinel-1 product: {selected['Name']}")
        print(f"📅 Date: {selected['ContentDate']['Start'][:10]}")
        print(f"🆔 ID: {selected['Id']}")
        download_product(USERNAME, PASSWORD, selected['Id'], selected['Name'])
    else:
        print("\n❌ No intersecting Sentinel-1 scenes found!")


# In[14]:


import requests
import json
import os
from shapely.wkt import loads as wkt_loads
from shapely.geometry import Polygon, shape
from datetime import datetime
from tqdm import tqdm

# ========= 🌐 PROXY SETTINGS (if required) =========
os.environ["http_proxy"] = "http://edcguest:edcguest@172.31.100.14:3128/"
os.environ["https_proxy"] = "http://edcguest:edcguest@172.31.100.14:3128/"

# ========= 1️⃣ AUTHENTICATION =========
def get_access_token(username, password):
    """Authenticate with Copernicus Data Space Ecosystem"""
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password"
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    print("✅ Authenticated successfully")
    return r.json()["access_token"]

# ========= 2️⃣ SEARCH SENTINEL-1 =========
def search_sentinel1(access_token, coords, start_date, end_date,
                     product_type='GRD', orbit_dir=None):
    """Search Sentinel-1 GRD products in a given area and date range"""
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    # Convert ROI to POLYGON string
    coord_str = ",".join([f"{lon} {lat}" for lon, lat in coords])
    geometry = f"POLYGON(({coord_str}))"
    print(f"Using Geometry: {geometry}")

    # Filter query (Updated for GRD products)
    filter_query = (
        f"Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{geometry}') and "
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq '{product_type}') and "
        f"ContentDate/Start ge {start_date}T00:00:00.000Z and "
        f"ContentDate/Start le {end_date}T23:59:59.999Z"
    )

    # Optional orbit direction
    if orbit_dir:
        filter_query += (
            f" and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'orbitDirection' "
            f"and att/OData.CSC.StringAttribute/Value eq '{orbit_dir}')"
        )

    params = {
        "$filter": filter_query,
        "$orderby": "ContentDate/Start asc",
        "$top": 100,
        "$select": "Id,Name,ContentDate,GeoFootprint"
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()

    # Debugging: Print the full API response to inspect
    response = r.json()
    print(json.dumps(response, indent=2))

    return response.get("value", [])

# ========= 3️⃣ PARSE FOOTPRINT =========
def parse_footprint(fp):
    if isinstance(fp, str):
        return wkt_loads(fp)
    elif isinstance(fp, dict):
        return shape(fp)
    else:
        raise ValueError("Unknown footprint format")

# ========= 4️⃣ GET INTERSECTING PRODUCTS =========
def get_intersecting_products(products, roi_polygon):
    """Return products whose footprints intersect the ROI"""
    intersecting = []
    for prod in products:
        try:
            footprint = parse_footprint(prod["GeoFootprint"])
            if footprint.intersects(roi_polygon):
                intersecting.append(prod)
        except Exception as e:
            print(f"⚠️ Error checking {prod.get('Name','unknown')}: {e}")
    return intersecting

# ========= 5️⃣ DOWNLOAD PRODUCT =========
def download_product(username, password, product_id, product_name, output_folder="S1_downloads"):
    """Download Sentinel-1 product with progress bar and fresh token"""
    os.makedirs(output_folder, exist_ok=True)

    # Get fresh token
    print("🔄 Getting fresh access token for download...")
    fresh_token = get_access_token(username, password)

    url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    headers = {"Authorization": f"Bearer {fresh_token}"}
    output_path = os.path.join(output_folder, f"{product_name}.zip")

    print(f"\n📥 Downloading: {product_name}")
    print(f"💾 Saving to: {output_path}")

    session = requests.Session()
    session.headers.update(headers)

    try:
        with session.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            print(f"📦 File size: {total_size / (1024**3):.2f} GB")

            chunk_size = 1024 * 1024  # 1 MB
            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True,
                         unit_divisor=1024, desc="Downloading") as pbar:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            print(f"✅ Download complete: {output_path}")
            return output_path
    except requests.exceptions.RequestException as e:
        print(f"❌ Download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

# ========= 6️⃣ MAIN EXECUTION =========
if __name__ == "__main__":
    USERNAME = "kskc.iirs@gmail.com"
    PASSWORD = "Sharath1141@@"

    # Example ROI (update with your coordinates)
    roi_coords = [
        [80.5024, 17.0213],
        [80.495, 16.8211],
        [80.7916, 16.8031],
        [80.8117, 17.0234],
        [80.5024, 17.0213]
    ]

    # February 1-28, 2017
    START_DATE = "2019-02-01"
    END_DATE = "2019-02-15"
    ORBIT_DIR = "DESCENDING"  # or "DESCENDING" or None

    print("🔐 Authenticating...")
    token = get_access_token(USERNAME, PASSWORD)

    print("\n🔍 Searching Sentinel-1 GRD scenes...")
    products_s1 = search_sentinel1(token, roi_coords, START_DATE, END_DATE, product_type='GRD', orbit_dir=ORBIT_DIR)
    print(f"🛰 Total Sentinel-1 scenes found: {len(products_s1)}")

    roi_poly = Polygon(roi_coords)
    intersecting = get_intersecting_products(products_s1, roi_poly)
    print(f"✅ Intersecting Sentinel-1 scenes: {len(intersecting)}")

    if intersecting:
        selected = intersecting[0]
        print(f"\n🎯 Selected Sentinel-1 product: {selected['Name']}")
        print(f"📅 Date: {selected['ContentDate']['Start'][:10]}")
        print(f"🆔 ID: {selected['Id']}")
        download_product(USERNAME, PASSWORD, selected['Id'], selected['Name'])
    else:
        print("\n❌ No intersecting Sentinel-1 GRD scenes found!")


# In[ ]:


import requests
import json
import os
from shapely.wkt import loads as wkt_loads
from shapely.geometry import Polygon, shape
from datetime import datetime
from tqdm import tqdm

# ========= PROXY (if needed) =========
os.environ["http_proxy"] = "http://edcguest:edcguest@172.31.100.14:3128/"
os.environ["https_proxy"] = "http://edcguest:edcguest@172.31.100.14:3128/"

# ========= 1️⃣ AUTHENTICATION =========
def get_access_token(username, password):
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password"
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    print("✅ Authenticated successfully")
    return r.json()["access_token"]

# ========= 2️⃣ SEARCH SENTINEL-2 L2A =========
def search_products(access_token, coords, start_date, end_date, cloud_cover=30):
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    coord_str = ",".join([f"{lon} {lat}" for lon, lat in coords])
    geometry = f"POLYGON(({coord_str}))"

    filter_query = (
        f"Collection/Name eq 'SENTINEL-2' and "
        f"contains(Name,'MSIL2A') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{geometry}') and "
        f"ContentDate/Start ge {start_date}T00:00:00.000Z and "
        f"ContentDate/Start le {end_date}T23:59:59.999Z and "
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
        f"and att/OData.CSC.DoubleAttribute/Value le {cloud_cover})"
    )

    params = {
        "$filter": filter_query,
        "$orderby": "ContentDate/Start asc",
        "$top": 100,
        "$select": "Id,Name,ContentDate,GeoFootprint"
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    return r.json().get("value", [])

# ========= 3️⃣ PARSE FOOTPRINT =========
def parse_footprint(fp):
    if isinstance(fp, str):
        return wkt_loads(fp)
    elif isinstance(fp, dict):
        return shape(fp)
    else:
        raise ValueError("Unknown footprint format")

# ========= 4️⃣ GET FULL COVERAGE PRODUCTS =========
def get_full_coverage_products(products, roi_polygon):
    full_cover = []
    for prod in products:
        try:
            footprint = parse_footprint(prod["GeoFootprint"])
            if footprint.contains(roi_polygon):
                full_cover.append(prod)
        except Exception as e:
            print(f"⚠️ Error checking {prod.get('Name','unknown')}: {e}")
    return full_cover

# ========= 5️⃣ DOWNLOAD PRODUCT WITH PROGRESS BAR =========
def download_product(username, password, product_id, product_name, output_folder="downloads"):
    """Download Sentinel-2 product with tqdm progress bar and fresh token"""
   
    os.makedirs(output_folder, exist_ok=True)
   
    # Get fresh token for download
    print("🔄 Getting fresh access token for download...")
    fresh_token = get_access_token(username, password)
   
    url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
    headers = {"Authorization": f"Bearer {fresh_token}"}
   
    output_path = os.path.join(output_folder, f"{product_name}.zip")
   
    print(f"\n📥 Downloading: {product_name}")
    print(f"💾 Saving to: {output_path}")
   
    # Use session for better connection handling
    session = requests.Session()
    session.headers.update(headers)
   
    try:
        # Get file size first
        with session.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
           
            total_size = int(r.headers.get('content-length', 0))
            print(f"📦 File size: {total_size / (1024**3):.2f} GB")
           
            # Download with progress bar
            chunk_size = 1024 * 1024  # 1MB chunks
           
            with open(output_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True,
                         unit_divisor=1024, desc="Downloading") as pbar:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
           
            print(f"✅ Download complete: {output_path}")
            return output_path
           
    except requests.exceptions.RequestException as e:
        print(f"❌ Download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

# ========= MAIN EXECUTION =========
USERNAME = "kskc.iirs@gmail.com"
PASSWORD = "Sharath1141@@"

roi_coords = [
        [80.5024, 17.0213],
        [80.495, 16.8211],
        [80.7916, 16.8031],
        [80.8117, 17.0234],
        [80.5024, 17.0213]
]

START_DATE = "2017-02-01"
END_DATE = "2017-02-28"
CLOUD_COVER = 30

# ---- RUN PIPELINE ----
print("🔐 Authenticating...")
token = get_access_token(USERNAME, PASSWORD)

print("\n🔍 Searching Sentinel-2 Level-2A scenes...")
products = search_products(token, roi_coords, START_DATE, END_DATE, CLOUD_COVER)
print(f"🛰 Total Level-2A scenes found: {len(products)}")

roi_poly = Polygon(roi_coords)
full_cover = get_full_coverage_products(products, roi_poly)
print(f"\n✅ Full coverage scenes: {len(full_cover)}")

if full_cover:
    # Select first full coverage product
    selected_product = full_cover[0]
    print(f"\n🎯 Selected product: {selected_product['Name']}")
    print(f"📅 Date: {selected_product['ContentDate']['Start'][:10]}")
    print(f"🆔 ID: {selected_product['Id']}")
   
    # Download
    download_product(USERNAME, PASSWORD, selected_product['Id'], selected_product['Name'])
else:
    print("\n❌ No full coverage scenes found!")

