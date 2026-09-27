"""
geo_tracker.py
High-precision location resolver for Windows Login Capture.
Uses Windows Native Wi-Fi positioning (~50-100m accuracy) with real reverse geocoding
for physical city/region identification (e.g. Coimbatore, Tamil Nadu) and IP fallback.
"""

import json
import subprocess
import urllib.request
import urllib.error

def get_windows_native_coordinates() -> tuple:
    """
    Queries Windows System.Device.Location API for high-precision Wi-Fi triangulation.
    Returns (lat, lon, accuracy_meters) or (None, None, None).
    """
    ps_cmd = (
        'Add-Type -AssemblyName System.Device; '
        '$w = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::High); '
        '$w.Start(); '
        '$timeout = 40; '
        'while ($w.Status -ne [System.Device.Location.GeoPositionStatus]::Ready -and $timeout -gt 0) { '
        '  Start-Sleep -Milliseconds 100; $timeout--; '
        '}; '
        '$pos = $w.Position.Location; '
        'if (-not $pos.IsUnknown) { '
        '  Write-Output "$($pos.Latitude)|$($pos.Longitude)|$($pos.HorizontalAccuracy)" '
        '}'
    )

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5.0
        )
        output = proc.stdout.strip()
        if output and "|" in output:
            parts = output.split("|")
            lat = float(parts[0])
            lon = float(parts[1])
            acc = float(parts[2]) if len(parts) > 2 else 0.0
            return lat, lon, acc
    except Exception:
        pass

    return None, None, None

def reverse_geocode_coordinates(lat: float, lon: float) -> dict:
    """Reverse geocodes coordinates to real physical City, Region, and Country."""
    # Method 1: BigDataCloud Reverse Geocoding API (Fast, Free, highly accurate for local cities)
    try:
        url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
        req = urllib.request.Request(url, headers={"User-Agent": "WindowsLoginCapture/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            city = data.get("city") or data.get("locality")
            region = data.get("principalSubdivision") or ""
            country = data.get("countryName") or "India"
            if city:
                return {"city": city, "region": region, "country": country}
    except Exception:
        pass

    # Method 2: OpenStreetMap Nominatim Fallback
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "WindowsLoginCapture/1.0 (SecuritySuite)"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            addr = data.get("address", {})
            city = addr.get("city") or addr.get("state_district") or addr.get("county") or addr.get("town") or addr.get("village")
            region = addr.get("state") or ""
            country = addr.get("country") or "India"
            if city:
                return {"city": city, "region": region, "country": country}
    except Exception:
        pass

    return None

def get_location_details() -> dict:
    """
    Attempts high-precision Windows location first, reverse-geocodes coordinates,
    and only falls back to IP geolocation if Wi-Fi coordinates are unavailable.
    """
    result = {
        "public_ip": "Offline / Unavailable",
        "city": "Unknown",
        "region": "Unknown",
        "country": "Unknown",
        "latitude": 0.0,
        "longitude": 0.0,
        "accuracy_m": 0.0,
        "maps_url": "",
        "source": "UNKNOWN",
        "location_status": "OFFLINE_PENDING"
    }

    # 1. Try Windows Native Wi-Fi Position (Most Accurate: ~50-100m)
    lat, lon, acc = get_windows_native_coordinates()
    if lat is not None and lon is not None:
        result["latitude"] = round(lat, 6)
        result["longitude"] = round(lon, 6)
        result["accuracy_m"] = round(acc, 1)
        result["maps_url"] = f"https://www.google.com/maps?q={result['latitude']},{result['longitude']}"
        result["source"] = "WINDOWS_WIFI_POSITION"
        result["location_status"] = "RESOLVED"

        # Reverse geocode the TRUE coordinates to get the actual physical city/region
        rev = reverse_geocode_coordinates(result["latitude"], result["longitude"])
        if rev:
            result["city"] = rev["city"]
            result["region"] = rev["region"]
            result["country"] = rev["country"]

    # 2. Query Public IP metadata (for IP forensics and fallback)
    try:
        url = "http://ip-api.com/json/?fields=status,country,regionName,city,lat,lon,query"
        req = urllib.request.Request(url, headers={"User-Agent": "WindowsLoginCapture/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "success":
                result["public_ip"] = data.get("query", "Unknown")
                
                # ONLY use IP city/region/coords if Wi-Fi triangulation was unavailable!
                if result["location_status"] != "RESOLVED":
                    result["city"] = data.get("city", "Unknown")
                    result["region"] = data.get("regionName", "Unknown")
                    result["country"] = data.get("country", "Unknown")
                    result["latitude"] = float(data.get("lat", 0.0))
                    result["longitude"] = float(data.get("lon", 0.0))
                    result["maps_url"] = f"https://www.google.com/maps?q={result['latitude']},{result['longitude']}"
                    result["source"] = "IP_GEOLOCATION"
                    result["location_status"] = "RESOLVED"
    except Exception:
        if result["location_status"] != "RESOLVED":
            result["location_status"] = "OFFLINE_PENDING"

    return result

# ----------------- SELF-TEST RUNNER -----------------
if __name__ == "__main__":
    print("--- Running upgraded geo_tracker.py self-test ---")
    info = get_location_details()
    
    print("\nLocation Status :", info["location_status"])
    print("Source Provider :", info["source"])
    print("Public IP       :", info["public_ip"])
    print("City / Region   :", f"{info['city']}, {info['region']}, {info['country']}")
    print("Coordinates     :", f"{info['latitude']}, {info['longitude']}")
    if info.get("accuracy_m"):
        print(f"Accuracy        : ~{info['accuracy_m']} meters")
    print("Google Maps Link:", info["maps_url"])
    print("\n--- Self-test completed ---")
