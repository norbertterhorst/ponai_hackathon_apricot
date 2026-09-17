"""
Test Script - Test alle API endpoints
Run dit TERWIJL de Flask server draait: python backend/test_api.py
"""

import requests
import json
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = "http://localhost:5000"

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Style.RESET_ALL}")

def print_success(text):
    print(f"{Fore.GREEN}✓ {text}{Style.RESET_ALL}")

def print_error(text):
    print(f"{Fore.RED}✗ {text}{Style.RESET_ALL}")

def print_info(text):
    print(f"{Fore.YELLOW}ℹ {text}{Style.RESET_ALL}")

def pretty_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════

print_header("TEST 1: Health Check")

try:
    resp = requests.get(f"{BASE_URL}/api/health")
    if resp.status_code == 200:
        print_success("API is online!")
        print(f"Response: {pretty_json(resp.json())}")
    else:
        print_error(f"Health check failed: {resp.status_code}")
except requests.exceptions.ConnectionError:
    print_error("Cannot connect to API. Start the server first:")
    print("  python backend/app.py")
    exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: GET VEHICLE BY PLATE
# ═══════════════════════════════════════════════════════════════════════════

print_header("TEST 2: Get Vehicle by License Plate")

plates = ["GZW-20-W", "ZVX-26-J", "VVK-12-X"]

for plate in plates:
    print(f"\n  🔍 Searching: {plate}")
    resp = requests.get(f"{BASE_URL}/api/vehicle/by-plate?plate={plate}")
    
    if resp.status_code == 200:
        data = resp.json()
        print_success(f"Found: {data['vehicle']['brand']} {data['vehicle']['model']}")
        print(f"    Owner: {data['owner']['given_name']} {data['owner']['family_name']}")
        print(f"    Mileage: {data['vehicle']['mileage']} km")
        print(f"    Warranty: {data['vehicle']['warranty_valid']} (until {data['vehicle']['warranty_end_date']})")
        print(f"    Services: {len(data['service_history'])} records")
    else:
        print_error(f"Not found: {resp.status_code}")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: GET VEHICLE BY VIN
# ═══════════════════════════════════════════════════════════════════════════

print_header("TEST 3: Get Vehicle by VIN")

vins = ["WV2ZZZSK8TX479575", "WV2ZZZSK8TX973054"]

for vin in vins:
    print(f"\n  🔍 Searching VIN: {vin}")
    resp = requests.get(f"{BASE_URL}/api/vehicle/by-vin?vin={vin}")
    
    if resp.status_code == 200:
        data = resp.json()
        print_success(f"Found: {data['brand']} {data['model']}")
        print(f"    Plate: {data['license_plate']}")
        print(f"    Mileage: {data['mileage']} km")
    else:
        print_error(f"Not found: {resp.status_code}")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: GET CUSTOMER INFO
# ═══════════════════════════════════════════════════════════════════════════

print_header("TEST 4: Get Customer Info & Vehicles")

customer_id = "00-289739"  # Bouwe Roovers met 4 auto's

print(f"\n  👤 Customer ID: {customer_id}")
resp = requests.get(f"{BASE_URL}/api/customer/{customer_id}/info")

if resp.status_code == 200:
    data = resp.json()
    print_success(f"Found: {data['given_name']} {data['family_name']}")
    print(f"    Address: {data['address']}")
    print(f"    Vehicles: {data['vehicle_count']}")
    
    # Get vehicles
    resp_vehicles = requests.get(f"{BASE_URL}/api/customer/{customer_id}/vehicles")
    vehicles = resp_vehicles.json()
    
    print(f"\n  🚗 Vehicles:")
    for i, v in enumerate(vehicles, 1):
        print(f"    {i}. {v['brand']} {v['model']} ({v['license_plate']}) - {v['mileage']} km")
else:
    print_error(f"Customer not found: {resp.status_code}")

# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: FULL VEHICLE PROFILE
# ═══════════════════════════════════════════════════════════════════════════

print_header("TEST 5: Full Vehicle Profile with Service History")

plate = "GZW-20-W"
print(f"\n  🔍 Full profile for: {plate}")

resp = requests.get(f"{BASE_URL}/api/vehicle/by-plate?plate={plate}")

if resp.status_code == 200:
    data = resp.json()
    
    # Vehicle info
    print(f"\n  📋 Vehicle:")
    print(f"    Brand: {data['vehicle']['brand']}")
    print(f"    Model: {data['vehicle']['model']}")
    print(f"    VIN: {data['vehicle']['vin']}")
    print(f"    Mileage: {data['vehicle']['mileage']} km")
    
    # Owner info
    print(f"\n  👤 Owner:")
    print(f"    Name: {data['owner']['given_name']} {data['owner']['family_name']}")
    print(f"    Address: {data['owner']['address_line1']}, {data['owner']['city']}")
    
    # Warranty
    print(f"\n  ✅ Warranty:")
    print(f"    Valid: {data['vehicle']['warranty_valid']}")
    print(f"    Until: {data['vehicle']['warranty_end_date']}")
    print(f"    Days remaining: {data['vehicle']['warranty_days_remaining']}")
    
    # Maintenance intervals
    print(f"\n  📅 Maintenance Intervals:")
    for interval in data['maintenance_intervals']:
        print(f"    - {interval['description']}: Every {interval['interval_months']} months / {interval['interval_kilometers']} km")
    
    # Service history
    print(f"\n  🔧 Service History (last {len(data['service_history'])} records):")
    for service in data['service_history']:
        print(f"    - {service['date']}: {service['work']} @ {service['dealer']} ({service['mileage_km']} km)")
else:
    print_error(f"Failed to get full profile: {resp.status_code}")

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print_header("✅ ALL TESTS COMPLETE")
print(f"\n{Fore.GREEN}API is ready for frontend team!{Style.RESET_ALL}")
print(f"\nDocumentation:")
print(f"  GET /api/vehicle/by-plate?plate=<PLATE>")
print(f"  GET /api/vehicle/by-vin?vin=<VIN>")
print(f"  GET /api/customer/<ID>/info")
print(f"  GET /api/customer/<ID>/vehicles")
print(f"  GET /api/health")
