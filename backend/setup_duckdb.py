"""
Setup DuckDB Database - Laadt alle JSONs in een lokale DuckDB
Run this ONCE: python backend/setup_duckdb.py
"""

import duckdb
import json
from pathlib import Path
import os

# Zorg dat we naar de juiste directory gaan
DATA_DIR = Path(__file__).parent.parent / "ai_werkorder_expert"
DB_PATH = Path(__file__).parent / "hackathon.duckdb"

print(f"📁 Data directory: {DATA_DIR}")
print(f"💾 Database file: {DB_PATH}")

# Verwijder oude DB als deze bestaat
if DB_PATH.exists():
    os.remove(DB_PATH)
    print("🗑️  Oude database verwijderd")

# Create connection
con = duckdb.connect(str(DB_PATH))

print("\n📊 Creating dimension tables...")

# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION TABLES
# ═══════════════════════════════════════════════════════════════════════════

con.execute("""
CREATE TABLE dim_customers (
    customer_id VARCHAR PRIMARY KEY,
    given_name VARCHAR,
    family_name VARCHAR,
    address_line1 VARCHAR,
    address_line2 VARCHAR,
    postal_code VARCHAR,
    city VARCHAR,
    country_code VARCHAR,
    status VARCHAR,
    language_code VARCHAR
)
""")

con.execute("""
CREATE TABLE dim_vehicles (
    vin VARCHAR PRIMARY KEY,
    license_plate VARCHAR,
    brand_name VARCHAR,
    model_name VARCHAR,
    model_type VARCHAR,
    fuel_type VARCHAR,
    mileage INTEGER,
    warranty_end_date VARCHAR,
    apk_renew_date VARCHAR,
    first_assigned_date VARCHAR,
    is_dutch_vehicle BOOLEAN
)
""")

con.execute("""
CREATE TABLE dim_maintenance_intervals (
    interval_id VARCHAR PRIMARY KEY,
    vehicle_vin VARCHAR,
    description VARCHAR,
    interval_months INTEGER,
    interval_kilometers INTEGER
)
""")

con.execute("""
CREATE TABLE dim_dealers (
    dealer_id VARCHAR PRIMARY KEY,
    dealer_name VARCHAR,
    street VARCHAR,
    postal_code VARCHAR,
    city VARCHAR,
    country VARCHAR,
    authorization_status VARCHAR
)
""")

print("📊 Creating fact tables...")

# ═══════════════════════════════════════════════════════════════════════════
# FACT TABLES
# ═══════════════════════════════════════════════════════════════════════════

con.execute("""
CREATE TABLE fact_vehicle_ownership (
    ownership_id VARCHAR PRIMARY KEY,
    vehicle_vin VARCHAR,
    customer_id VARCHAR,
    relationship_type VARCHAR
)
""")

con.execute("""
CREATE TABLE fact_service_history (
    service_id VARCHAR PRIMARY KEY,
    vehicle_vin VARCHAR,
    service_date VARCHAR,
    mileage_km INTEGER,
    work_description VARCHAR,
    dealer_name VARCHAR,
    service_kind VARCHAR,
    mobility_guarantee BOOLEAN
)
""")

con.execute("""
CREATE TABLE fact_recalls (
    recall_id VARCHAR PRIMARY KEY,
    vehicle_vin VARCHAR,
    recall_source VARCHAR,
    status VARCHAR
)
""")

con.execute("""
CREATE TABLE fact_repairs (
    repair_id VARCHAR PRIMARY KEY,
    vehicle_vin VARCHAR,
    invoice_number VARCHAR,
    order_number VARCHAR,
    acceptance_date VARCHAR,
    mileage_km INTEGER,
    warranty BOOLEAN,
    is_maintenance BOOLEAN
)
""")

con.execute("""
CREATE TABLE fact_repair_labor (
    labor_id VARCHAR PRIMARY KEY,
    repair_id VARCHAR,
    line_number INTEGER,
    description VARCHAR,
    is_maintenance BOOLEAN,
    amount DECIMAL(10, 2)
)
""")

con.execute("""
CREATE TABLE fact_contracts (
    contract_id VARCHAR PRIMARY KEY,
    vehicle_vin VARCHAR,
    customer_id VARCHAR,
    contract_type VARCHAR,
    start_date VARCHAR,
    end_date VARCHAR,
    contract_data VARCHAR
)
""")

con.execute("""
CREATE TABLE fact_vehicle_current_state (
    vehicle_vin VARCHAR PRIMARY KEY,
    current_customer_id VARCHAR,
    current_mileage INTEGER,
    last_service_date VARCHAR,
    next_service_date VARCHAR,
    warranty_status VARCHAR,
    last_appointment_date VARCHAR,
    updated_at VARCHAR
)
""")

con.execute("""
CREATE TABLE dim_pon_packages (
    pon_code VARCHAR PRIMARY KEY,
    pon_name VARCHAR,
    pon_description VARCHAR,
    allowed_time_hours DECIMAL(5, 2),
    price_inclusive DECIMAL(10, 2),
    price_exclusive DECIMAL(10, 2),
    duration_category VARCHAR
)
""")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════

print("\n👤 Loading customers...")
customer_count = 0
for file in (DATA_DIR / "customer").glob("*.json"):
    try:
        with open(file) as f:
            data = json.load(f)
            cust = data[0]['customer']['customer']
            addr = cust['addresses']['physical']['formattedAddress']
            
            con.execute("""
            INSERT INTO dim_customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                cust['customerId'],
                cust['individual'].get('givenName', ''),
                cust['individual'].get('familyName', ''),
                addr.get('line1', ''),
                addr.get('line2', ''),
                cust['addresses']['physical'].get('postalCode', ''),
                cust['addresses']['physical'].get('city', ''),
                cust['addresses']['physical'].get('countryCode', ''),
                cust.get('status', ''),
                cust.get('languageCode', '')
            ])
            customer_count += 1
    except Exception as e:
        print(f"  ⚠️  Fout bij {file.name}: {e}")

print(f"  ✓ {customer_count} customers geladen")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - VEHICLES
# ═══════════════════════════════════════════════════════════════════════════

print("\n🚗 Loading vehicles...")
vehicle_count = 0
for file in (DATA_DIR / "car" / "vehicle_data").glob("*.json"):
    try:
        with open(file) as f:
            data = json.load(f)
            veh = data[0]['vehicle_data']
            
            con.execute("""
            INSERT INTO dim_vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                veh['vin'],
                veh.get('licenseplate', ''),
                veh.get('brandName', ''),
                veh.get('modelName', ''),
                veh.get('modelType', ''),
                veh.get('fuelType', ''),
                veh.get('mileage', 0),
                veh.get('warrantyEndDate'),
                veh.get('apkRenewDate', ''),
                veh.get('firstAssignedDate', ''),
                veh.get('isDutchVehicle', False)
            ])
            vehicle_count += 1
    except Exception as e:
        print(f"  ⚠️  Fout bij {file.name}: {e}")

print(f"  ✓ {vehicle_count} vehicles geladen")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - VEHICLE RELATIONS
# ═══════════════════════════════════════════════════════════════════════════

print("\n🔗 Loading vehicle ownership...")
ownership_count = 0
for file in (DATA_DIR / "car" / "vehicle_relations").glob("*.json"):
    try:
        vin = file.stem
        with open(file) as f:
            data = json.load(f)
            for rel in data:
                rel_data = rel['vehicle_relations_driver']
                customer_id = rel_data['customer']['customerId']
                
                con.execute("""
                INSERT INTO fact_vehicle_ownership VALUES (?, ?, ?, ?)
                """, [
                    f"{vin}_{customer_id}",
                    vin,
                    customer_id,
                    rel_data['type']
                ])
                ownership_count += 1
    except Exception as e:
        print(f"  ⚠️  Fout bij {file.name}: {e}")

print(f"  ✓ {ownership_count} vehicle ownerships geladen")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - SERVICE HISTORY
# ═══════════════════════════════════════════════════════════════════════════

print("\n🔧 Loading service history...")
service_count = 0
for file in (DATA_DIR / "maintenance_history" / "service_book").glob("*.json"):
    try:
        vin = file.stem
        with open(file) as f:
            data = json.load(f)
            for entry in data[0]['service_book']['entries']:
                con.execute("""
                INSERT INTO fact_service_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    entry['documentUID'],
                    vin,
                    entry['acceptanceDate'][:10],
                    entry['mileage']['value'],
                    entry['workDescription'],
                    entry.get('dealerAddress', {}).get('name', ''),
                    entry.get('serviceKind', ''),
                    entry.get('mobilityGuarantee', False)
                ])
                service_count += 1
    except Exception as e:
        print(f"  ⚠️  Fout bij {file.name}: {e}")

print(f"  ✓ {service_count} service records geladen")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - MAINTENANCE INTERVALS
# ═══════════════════════════════════════════════════════════════════════════

print("\n📅 Loading maintenance intervals...")
interval_count = 0
for file in (DATA_DIR / "service_intervals" / "regular_maintenance").glob("*.json"):
    try:
        vin = file.stem
        with open(file) as f:
            data = json.load(f)
            for interval in data[0]['regular_maintenance']['intervallen']:
                con.execute("""
                INSERT INTO dim_maintenance_intervals VALUES (?, ?, ?, ?, ?)
                """, [
                    f"{vin}_{interval['omschrijving']}",
                    vin,
                    interval['omschrijving'],
                    interval['interval_tijd_maanden'],
                    interval['interval_kilometers']
                ])
                interval_count += 1
    except Exception as e:
        print(f"  ⚠️  Fout bij {file.name}: {e}")

print(f"  ✓ {interval_count} maintenance intervals geladen")

# ═══════════════════════════════════════════════════════════════════════════
# BUILD DEALERS from service history
# ═══════════════════════════════════════════════════════════════════════════

print("\n🏢 Building dealers table from service history...")
dealer_count = 0
dealers = con.execute("""
    SELECT DISTINCT dealer_name FROM fact_service_history WHERE dealer_name IS NOT NULL AND dealer_name != ''
""").fetchall()

for dealer_tuple in dealers:
    dealer_name = dealer_tuple[0]
    con.execute("""
    INSERT INTO dim_dealers VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        dealer_name,  # dealer_id = name (unique key)
        dealer_name,
        '',  # street
        '',  # postal_code
        '',  # city
        'NL',  # country
        'ACTIVE'  # authorization_status
    ])
    dealer_count += 1

print(f"  ✓ {dealer_count} dealers extracted")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - PON PACKAGES (Maintenance pricing & duration)
# ═══════════════════════════════════════════════════════════════════════════

print("\n💰 Loading PON Maintenance Packages...")
pon_count = 0
for file in (DATA_DIR / "maintenance_packages" / "pon_packages").glob("*.json"):
    try:
        with open(file) as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                pon_data = data[0].get('pon_packages', {})
                if isinstance(pon_data, dict):
                    for pon in pon_data.get('pon', []):
                        for child in pon.get('children', []):
                            prices = child.get('prices', [])
                            allowed_time = child.get('allowedTime', 0)
                            
                            # Get latest price
                            price_incl = None
                            price_excl = None
                            if prices:
                                price_incl = prices[0].get('priceInclusive', 0)
                                price_excl = prices[0].get('priceExclusive', 0)
                            
                            # Categorize by duration
                            if allowed_time <= 2:
                                duration = "≤2 uur"
                            elif allowed_time <= 8:
                                duration = "1 werkdag"
                            else:
                                duration = "langer"
                            
                            con.execute("""
                            INSERT INTO dim_pon_packages VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, [
                                child.get('code', f"PON_{pon_count}"),
                                child.get('name', ''),
                                child.get('description', ''),
                                allowed_time,
                                price_incl,
                                price_excl,
                                duration
                            ])
                            pon_count += 1
    except Exception as e:
        pass  # Silent fail voor PON packages

print(f"  ✓ {pon_count} PON maintenance packages geladen")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - RECALLS
# ═══════════════════════════════════════════════════════════════════════════

print("\n⚠️  Loading recalls...")
recall_count = 0
for file in (DATA_DIR / "recalls" / "recalls_open_elsa").glob("*.json"):
    try:
        vin = file.stem
        with open(file) as f:
            data = json.load(f)
            recall_data = data[0]['recalls_open_elsa']
            
            # Check if there are any recalls
            if recall_data.get('openFieldCampaigns'):
                for recall in recall_data['openFieldCampaigns']:
                    con.execute("""
                    INSERT INTO fact_recalls VALUES (?, ?, ?, ?)
                    """, [
                        f"{vin}_elsa_{recall_count}",
                        vin,
                        "ELSA",
                        "OPEN"
                    ])
                    recall_count += 1
    except Exception as e:
        pass  # Silent fail voor recalls

print(f"  ✓ {recall_count} recalls geladen")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA - CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════

print("\n📋 Loading contracts...")
contract_count = 0
for file in (DATA_DIR / "car" / "contracts").glob("*.json"):
    try:
        vin = file.stem
        with open(file) as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                contract_data = data[0].get('contracts', {})
                if isinstance(contract_data, dict):
                    for contract in contract_data.get('contractDetails', []):
                        customer_id = contract.get('customerId', '')
                        if customer_id:
                            con.execute("""
                            INSERT INTO fact_contracts VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, [
                                contract.get('contractId', f"{vin}_{contract_count}"),
                                vin,
                                customer_id,
                                contract.get('contractType', ''),
                                contract.get('startDate', ''),
                                contract.get('endDate', ''),
                                json.dumps(contract)
                            ])
                            contract_count += 1
    except Exception as e:
        pass  # Silent fail voor contracts

print(f"  ✓ {contract_count} contracts geladen")

# ═══════════════════════════════════════════════════════════════════════════
# BUILD VEHICLE CURRENT STATE (Summary table)
# ═══════════════════════════════════════════════════════════════════════════

print("\n📊 Building vehicle current state...")
state_count = 0
for vehicle in con.execute("SELECT DISTINCT vin FROM dim_vehicles").fetchall():
    vin = vehicle[0]
    
    # Get current customer
    cust = con.execute(f"""
        SELECT customer_id FROM fact_vehicle_ownership 
        WHERE vehicle_vin = '{vin}' LIMIT 1
    """).fetchone()
    customer_id = cust[0] if cust else None
    
    # Get last service
    service = con.execute(f"""
        SELECT service_date, mileage_km FROM fact_service_history 
        WHERE vehicle_vin = '{vin}' 
        ORDER BY service_date DESC LIMIT 1
    """).fetchone()
    last_service = service[0] if service else None
    last_mileage = service[1] if service else 0
    
    # Get warranty status
    vehicle_data = con.execute(f"""
        SELECT warranty_end_date FROM dim_vehicles WHERE vin = '{vin}'
    """).fetchone()
    warranty_end = vehicle_data[0] if vehicle_data else None
    warranty_status = "VALID" if warranty_end and warranty_end > "2026-09-17" else "EXPIRED"
    
    con.execute("""
    INSERT INTO fact_vehicle_current_state VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        vin,
        customer_id,
        last_mileage,
        last_service,
        None,  # next_service_date - kan berekend worden
        warranty_status,
        None,  # last_appointment_date
        "2026-09-17"  # updated_at
    ])
    state_count += 1

print(f"  ✓ {state_count} vehicle states built")

# Commit all changes
con.commit()

# ═══════════════════════════════════════════════════════════════════════════
# CREATE INDEXES
# ═══════════════════════════════════════════════════════════════════════════

print("\n⚡ Creating indexes...")
con.execute("CREATE INDEX idx_vehicle_license_plate ON dim_vehicles(license_plate)")
con.execute("CREATE INDEX idx_vehicle_vin ON dim_vehicles(vin)")
con.execute("CREATE INDEX idx_ownership_vin ON fact_vehicle_ownership(vehicle_vin)")
con.execute("CREATE INDEX idx_ownership_customer ON fact_vehicle_ownership(customer_id)")
con.execute("CREATE INDEX idx_service_vin ON fact_service_history(vehicle_vin)")
con.execute("CREATE INDEX idx_recalls_vin ON fact_recalls(vehicle_vin)")
con.execute("CREATE INDEX idx_repairs_vin ON fact_repairs(vehicle_vin)")
con.execute("CREATE INDEX idx_contracts_vin ON fact_contracts(vehicle_vin)")
con.execute("CREATE INDEX idx_contracts_customer ON fact_contracts(customer_id)")
con.execute("CREATE INDEX idx_current_state_vin ON fact_vehicle_current_state(vehicle_vin)")
con.execute("CREATE INDEX idx_pon_code ON dim_pon_packages(pon_code)")

con.commit()
con.close()

print("\n" + "="*60)
print("✅ DATABASE SETUP COMPLETE!")
print("="*60)
print(f"Database location: {DB_PATH}")
print(f"\nRun: python backend/app.py")
print("="*60)
