"""
Flask API - Werkorder Expert
Query voertuigen op kenteken, VIN, of klant ID
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import duckdb
import json
from pathlib import Path
from datetime import datetime

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
CORS(app)

# Connect to DuckDB
DB_PATH = Path(__file__).parent / "hackathon.duckdb"

if not DB_PATH.exists():
    print("❌ Database not found!")
    print("Run: python backend/setup_duckdb.py")
    exit(1)

con = duckdb.connect(str(DB_PATH), read_only=True)

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def row_to_dict(row):
    """Convert DuckDB row to dictionary"""
    if row is None:
        return None
    return dict(row) if hasattr(row, 'keys') else row

def is_vehicle_leased(vin):
    """
    Check if vehicle is leased by reading ROB-net/leaseContract/{vin}.json
    Returns: True if leased, False if owned/not found
    """
    import json
    lease_file = Path(__file__).parent.parent / "ai_werkorder_expert" / "ROB-net" / "leaseContract" / f"{vin}.json"
    
    try:
        if lease_file.exists():
            with open(lease_file) as f:
                data = json.load(f)
                if data and len(data) > 0:
                    lease_contract = data[0].get("leaseContract")
                    return lease_contract is not None  # If leaseContract exists and is not null, vehicle is leased
    except:
        pass
    
    return False  # Default to not leased

def get_tyre_info(vin):
    """Read tyre information from car/tyres/{vin}.json if available"""
    tyre_file = Path(__file__).parent.parent / "ai_werkorder_expert" / "car" / "tyres" / f"{vin}.json"

    try:
        if tyre_file.exists():
            with open(tyre_file) as f:
                data = json.load(f)
                if data and len(data) > 0:
                    return data[0].get("tyres")
    except:
        pass

    return None

def get_price_from_package(package, is_leased):
    """
    Extract the correct price from a package based on lease status.
    Looks for matching entry in prices array with lease=true/false.
    Falls back to price_incl/price_excl if prices array not available.
    """
    if not package:
        return None, None
    
    # If package has prices array with lease variants, find the correct one
    prices_array = package.get("prices", [])
    if prices_array and isinstance(prices_array, list):
        for price_entry in prices_array:
            if isinstance(price_entry, dict) and price_entry.get("lease") == is_leased:
                return price_entry.get("priceExclusive"), price_entry.get("priceInclusive")
    
    # Fallback: use price_incl/price_excl fields (they default to lease=false)
    return package.get("price_excl"), package.get("price_incl")

def apply_lease_pricing_to_package(package, is_leased):
    """
    Update package's price_excl and price_incl fields based on lease status.
    Returns a modified copy of the package with correct pricing.
    """
    if not package:
        return None
    
    # Make a shallow copy to avoid modifying the original
    pkg_copy = package.copy()
    
    # Get the correct prices for this lease status
    price_excl, price_incl = get_price_from_package(package, is_leased)
    
    # Update the top-level price fields
    if price_excl is not None:
        pkg_copy["price_excl"] = price_excl
    if price_incl is not None:
        pkg_copy["price_incl"] = price_incl
    
    return pkg_copy

def days_until_date(date_str):
    """Calculate days until a date"""
    if not date_str:
        return None
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now()
        delta = (target - today).days
        return delta
    except:
        return None

def is_warranty_valid(warranty_end_date):
    """Check if warranty is still valid"""
    days = days_until_date(warranty_end_date)
    return days is not None and days > 0

def find_package_for_maintenance(maintenance_type, pon_packages):
    """
    Match maintenance type with corresponding package.
    Uses multi-level fallback strategy since different vehicles have different packages.
    
    MATCHING STRATEGY:
    - Inspectie → "Inspectieservice"
    - Olieservice/olie → Try: "Olieservice" → "Kleine Onderhoudsservice" → "Grote Onderhoudsservice"
    - Always prefer packages WITH PRICES
    """
    if not maintenance_type or not pon_packages:
        return None
    
    mt_lower = maintenance_type.lower().strip()
    
    # ═══════════════════════════════════════════════════════════════════
    # LEVEL 1: EXACT MATCHES
    # ═══════════════════════════════════════════════════════════════════
    
    for pkg in pon_packages:
        if not pkg or not isinstance(pkg, dict):
            continue
        pkg_name_lower = (pkg.get('name', "") or "").lower().strip()
        
        # Inspectie → Inspectieservice
        if "inspectie" in mt_lower and pkg_name_lower == "inspectieservice":
            return pkg
        
        # Oil services → Exact "Olieservice" match
        if "olie" in mt_lower and pkg_name_lower == "olieservice":
            return pkg
    
    # ═══════════════════════════════════════════════════════════════════
    # LEVEL 2: FALLBACK CHAINS (for when exact match not available)
    # ═══════════════════════════════════════════════════════════════════
    
    if "olie" in mt_lower or "onderhoud" in mt_lower:
        # Oil maintenance fallback chain: try packages in order
        # 1. Kleine Onderhoudsservice (small oil service)
        # 2. Grote Onderhoudsservice (large maintenance with oil)
        # 3. Longlife Onderhoudsservice (variable maintenance with oil)
        fallback_options = [
            "kleine onderhoudsservice",
            "grote onderhoudsservice",
            "longlife onderhoudsservice",
            "onderhoudspakket"
        ]
        
        for fallback_name in fallback_options:
            for pkg in pon_packages:
                if not pkg or not isinstance(pkg, dict):
                    continue
                pkg_name_lower = (pkg.get('name', "") or "").lower().strip()
                
                if fallback_name in pkg_name_lower and (pkg.get('price_incl') or pkg.get('price_excl')):
                    return pkg
    
    # ═══════════════════════════════════════════════════════════════════
    # LEVEL 3: LAST RESORT - ANY service with price
    # ═══════════════════════════════════════════════════════════════════
    
    for pkg in pon_packages:
        if not pkg or not isinstance(pkg, dict):
            continue
        
        # Only return packages that HAVE PRICES (skip free services)
        if pkg.get('price_incl') or pkg.get('price_excl'):
            pkg_name_lower = (pkg.get('name', "") or "").lower().strip()
            if any(x in pkg_name_lower for x in ["onderhoud", "service", "maintenance"]):
                return pkg
    
    return None

# ═══════════════════════════════════════════════════════════════════════════
# SWAGGER / OPENAPI SPEC
# ═══════════════════════════════════════════════════════════════════════════

def get_openapi_spec():
    """Generate OpenAPI 3.0 specification"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "🚗 Werkorder Expert API",
            "version": "1.0.0",
            "description": "Vehicle diagnostic API for service workorder management"
        },
        "servers": [
            {"url": "https://christina-temperature-meant-blank.trycloudflare.com", "description": "Production (Cloudflare Tunnel)"},
            {"url": "http://localhost:5003", "description": "Development"}
        ],
        "paths": {
            "/api/vehicle/diagnostic/{plate}": {
                "get": {
                    "summary": "Complete vehicle diagnostic",
                    "description": "Get full vehicle info, required maintenance, recalls, and available service packages",
                    "tags": ["Vehicle"],
                    "parameters": [
                        {"name": "plate", "in": "path", "required": True, "schema": {"type": "string"}, "example": "WDX-90-M"}
                    ],
                    "responses": {
                        "200": {
                            "description": "Vehicle diagnostic data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "vehicle": {
                                                "type": "object",
                                                "properties": {
                                                    "vin": {"type": "string", "example": "WVWZZZAW4RU404624"},
                                                    "license_plate": {"type": "string", "example": "WDX-90-M"},
                                                    "brand": {"type": "string", "example": "Volkswagen"},
                                                    "model": {"type": "string", "example": "Polo (6) GP"},
                                                    "mileage_km": {"type": "number", "example": 75500},
                                                    "fuel_type": {"type": "string"},
                                                    "is_leased": {"type": "boolean", "description": "True if vehicle has active lease contract"},
                                                    "tyres": {
                                                        "type": "object",
                                                        "nullable": True,
                                                        "properties": {
                                                            "vin": {"type": "string"},
                                                            "type": {"type": "string", "example": "winter"},
                                                            "profileDepthMm": {"type": "number"},
                                                            "location": {"type": "string"}
                                                        }
                                                    },
                                                    "warranty_valid": {"type": "boolean"},
                                                    "apk_renew_days": {"type": "integer"}
                                                }
                                            },
                                            "owner": {
                                                "type": "object",
                                                "properties": {
                                                    "customer_id": {"type": "string"},
                                                    "name": {"type": "string"},
                                                    "address": {"type": "string"},
                                                    "postal_code": {"type": "string"}
                                                }
                                            },
                                            "last_service": {
                                                "type": "object",
                                                "properties": {
                                                    "date": {"type": "string", "format": "date"},
                                                    "mileage_km": {"type": "number"},
                                                    "work": {"type": "string"},
                                                    "dealer": {"type": "string"}
                                                }
                                            },
                                            "maintenance_required": {"type": "boolean"},
                                            "required_maintenance": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "type": {"type": "string", "example": "Inspectie"},
                                                        "urgency": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                                                        "details": {"type": "object"},
                                                        "duration_hours": {"type": "number", "example": 1.0},
                                                        "estimated_cost": {
                                                            "type": "object",
                                                            "properties": {
                                                                "price_excl": {"type": "number", "example": 150.0},
                                                                "price_incl": {"type": "number", "example": 181.5}
                                                            }
                                                        },
                                                        "package": {
                                                            "type": "object",
                                                            "description": "Complete PON package object with pricing and details",
                                                            "properties": {
                                                                "code": {"type": "string"},
                                                                "name": {"type": "string"},
                                                                "description": {"type": "string"},
                                                                "category": {"type": "string"},
                                                                "category_code": {"type": "string"},
                                                                "duration_hours": {"type": "number"},
                                                                "duration_category": {"type": "string"},
                                                                "price_excl": {"type": "number"},
                                                                "price_incl": {"type": "number"},
                                                                "type": {"type": "string", "example": "PON"},
                                                                "is_owner_task": {"type": "boolean"},
                                                                "contents": {
                                                                    "type": "array",
                                                                    "items": {
                                                                        "type": "object",
                                                                        "properties": {
                                                                            "amount": {"type": "number"},
                                                                            "code": {"type": "string"},
                                                                            "description": {"type": "string"},
                                                                            "type": {"type": "string", "example": "ppsPart"}
                                                                        }
                                                                    }
                                                                },
                                                                "prices": {
                                                                    "type": "array",
                                                                    "items": {
                                                                        "type": "object",
                                                                        "properties": {
                                                                            "startDate": {"type": "string", "format": "date-time"},
                                                                            "endDate": {"type": "string", "format": "date-time"},
                                                                            "lease": {"type": "boolean"},
                                                                            "priceExclusive": {"type": "number"},
                                                                            "priceInclusive": {"type": "number"}
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            },
                                            "required_maintenance_summary": {
                                                "type": "object",
                                                "properties": {
                                                    "total_cost_excl": {"type": "number", "example": 406.61},
                                                    "total_cost_incl": {"type": "number", "example": 492.0},
                                                    "total_duration_hours": {"type": "number", "example": 1.5},
                                                    "count": {"type": "integer", "example": 2}
                                                }
                                            },
                                            "recalls": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "id": {"type": "string"},
                                                        "source": {"type": "string", "example": "ELSA"},
                                                        "status": {"type": "string", "example": "OPEN"}
                                                    }
                                                }
                                            },
                                            "available_packages": {
                                                "type": "object",
                                                "properties": {
                                                    "≤2 uur": {
                                                        "type": "object",
                                                        "properties": {
                                                            "regular": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "code": {"type": "string"},
                                                                        "name": {"type": "string"},
                                                                        "category": {"type": "string"},
                                                                        "category_code": {"type": "string"},
                                                                        "duration_hours": {"type": "number"},
                                                                        "price_incl": {"type": "number"},
                                                                        "price_excl": {"type": "number"}
                                                                    }
                                                                }
                                                            },
                                                            "owner_tasks": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "code": {"type": "string"},
                                                                        "name": {"type": "string"},
                                                                        "note": {"type": "string", "example": "ORU/OTA - ausgevoerd door eigenaar"},
                                                                        "category": {"type": "string"},
                                                                        "duration_hours": {"type": "number"},
                                                                        "price_incl": {"type": "number"}
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    },
                                                    "1 werkdag": {"type": "object"},
                                                    "langer": {"type": "object"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"description": "Invalid plate"}
                    }
                }
            },
            "/api/vehicle/by-plate": {
                "get": {
                    "summary": "Query vehicle by license plate",
                    "tags": ["Vehicle"],
                    "parameters": [
                        {"name": "plate", "in": "query", "required": True, "schema": {"type": "string"}, "example": "WDX-90-M"}
                    ],
                    "responses": {"200": {"description": "Vehicle data including tyre information"}}
                }
            },
            "/api/customer/by-plate": {
                "get": {
                    "summary": "Get customer ID by license plate",
                    "description": "Resolve a license plate to the related customer ID(s) using vehicle ownership data",
                    "tags": ["Customer"],
                    "parameters": [
                        {"name": "plate", "in": "query", "required": True, "schema": {"type": "string"}, "example": "XTR-86-Z"}
                    ],
                    "responses": {"200": {"description": "Customer relation data"}}
                }
            },
            "/api/vehicle/by-vin": {
                "get": {
                    "summary": "Query vehicle by VIN",
                    "tags": ["Vehicle"],
                    "parameters": [
                        {"name": "vin", "in": "query", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "Vehicle data including tyre information"}}
                }
            },
            "/api/customer/{customer_id}/info": {
                "get": {
                    "summary": "Get customer information",
                    "tags": ["Customer"],
                    "parameters": [
                        {"name": "customer_id", "in": "path", "required": True, "schema": {"type": "string"}, "example": "00-114464"}
                    ],
                    "responses": {"200": {"description": "Customer data"}}
                }
            },
            "/api/customer/{customer_id}/vehicles": {
                "get": {
                    "summary": "Get all vehicles for a customer",
                    "tags": ["Customer"],
                    "parameters": [
                        {"name": "customer_id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "List of vehicles including tyre information"}}
                }
            },
            "/api/health": {
                "get": {
                    "summary": "API health check",
                    "tags": ["System"],
                    "responses": {"200": {"description": "API status"}}
                }
            }
        }
    }

# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
def index():
    """Serve the HTML frontend"""
    return render_template('index.html')

@app.route('/swagger', methods=['GET'])
def swagger_ui():
    """Serve Swagger UI"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚗 Werkorder Expert API - Swagger UI</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@3/swagger-ui.css">
        <style>
            body { margin: 0; padding: 0; }
            .topbar { display: none; }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
        <script>
            const ui = SwaggerUIBundle({
                url: "/api/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true
            })
            window.onload = function() {
                window.ui = ui
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/openapi.json', methods=['GET'])
def openapi_json():
    """Serve OpenAPI specification"""
    return jsonify(get_openapi_spec())

@app.route('/api/vehicle/by-plate', methods=['GET'])
def get_vehicle_by_plate():
    """
    Query vehicle by license plate
    Example: /api/vehicle/by-plate?plate=GZW-20-W
    """
    plate = request.args.get('plate', '').upper()
    
    if not plate:
        return jsonify({"error": "Plate parameter required"}), 400
    
    try:
        # Query vehicle + owner info
        result = con.execute(f"""
        SELECT 
            v.vin,
            v.license_plate,
            v.brand_name,
            v.model_name,
            v.mileage,
            v.fuel_type,
            v.warranty_end_date,
            v.apk_renew_date,
            v.first_assigned_date,
            c.customer_id,
            c.given_name,
            c.family_name,
            c.address_line1,
            c.address_line2,
            c.city,
            c.postal_code
        FROM dim_vehicles v
        LEFT JOIN fact_vehicle_ownership fvo ON v.vin = fvo.vehicle_vin
        LEFT JOIN dim_customers c ON fvo.customer_id = c.customer_id
        WHERE v.license_plate = ?
        LIMIT 1
        """, [plate]).fetchall()
        
        if not result:
            return jsonify({"error": "Vehicle not found"}), 404
        
        row = result[0]
        vin = row[0]
        
        # Get maintenance intervals
        intervals = con.execute(f"""
        SELECT description, interval_months, interval_kilometers
        FROM dim_maintenance_intervals
        WHERE vehicle_vin = ?
        """, [vin]).fetchall()
        
        # Get service history (last 5)
        services = con.execute(f"""
        SELECT service_date, work_description, dealer_name, mileage_km
        FROM fact_service_history
        WHERE vehicle_vin = ?
        ORDER BY service_date DESC
        LIMIT 5
        """, [vin]).fetchall()
        
        # Build response
        response = {
            "vehicle": {
                "vin": row[0],
                "license_plate": row[1],
                "brand": row[2],
                "model": row[3],
                "mileage": row[4],
                "fuel_type": row[5],
                "warranty_end_date": row[6],
                "warranty_days_remaining": days_until_date(row[6]),
                "warranty_valid": is_warranty_valid(row[6]),
                "apk_renew_date": row[7],
                "first_assigned_date": row[8],
                "tyres": get_tyre_info(vin)
            },
            "owner": {
                "customer_id": row[9],
                "given_name": row[10] or "",
                "family_name": row[11] or "",
                "address_line1": row[12] or "",
                "address_line2": row[13] or "",
                "city": row[14] or "",
                "postal_code": row[15] or ""
            },
            "maintenance_intervals": [
                {
                    "description": i[0],
                    "interval_months": i[1],
                    "interval_kilometers": i[2]
                } for i in intervals
            ],
            "service_history": [
                {
                    "date": s[0],
                    "work": s[1],
                    "dealer": s[2],
                    "mileage_km": s[3]
                } for s in services
            ]
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/customer/by-plate', methods=['GET'])
def get_customer_id_by_plate():
    """
    Get customer ID(s) by license plate
    Example: /api/customer/by-plate?plate=XTR-86-Z
    """
    plate = request.args.get('plate', '')
    plate_key = plate.replace('-', '').upper()

    if not plate_key:
        return jsonify({"error": "Plate parameter required"}), 400

    try:
        result = con.execute("""
        SELECT
            v.license_plate,
            v.vin,
            fvo.relationship_type,
            fvo.customer_id,
            c.given_name,
            c.family_name
        FROM dim_vehicles v
        JOIN fact_vehicle_ownership fvo ON v.vin = fvo.vehicle_vin
        LEFT JOIN dim_customers c ON fvo.customer_id = c.customer_id
        WHERE upper(replace(v.license_plate, '-', '')) = ?
        ORDER BY fvo.relationship_type, fvo.customer_id
        """, [plate_key]).fetchall()

        if not result:
            return jsonify({"error": "Customer relation not found for license plate"}), 404

        response = {
            "license_plate": result[0][0],
            "vin": result[0][1],
            "customers": [
                {
                    "relation_type": row[2],
                    "customer_id": row[3],
                    "name": f"{row[4] or ''} {row[5] or ''}".strip()
                } for row in result
            ]
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vehicle/by-vin', methods=['GET'])
def get_vehicle_by_vin():
    """
    Query vehicle by VIN (chassis number)
    Example: /api/vehicle/by-vin?vin=WV2ZZZSK8TX479575
    """
    vin = request.args.get('vin', '').upper()
    
    if not vin:
        return jsonify({"error": "VIN parameter required"}), 400
    
    try:
        result = con.execute(f"""
        SELECT 
            v.vin,
            v.license_plate,
            v.brand_name,
            v.model_name,
            v.mileage,
            v.fuel_type,
            v.warranty_end_date,
            v.apk_renew_date
        FROM dim_vehicles v
        WHERE v.vin = ?
        LIMIT 1
        """, [vin]).fetchall()
        
        if not result:
            return jsonify({"error": "Vehicle not found"}), 404
        
        row = result[0]
        
        response = {
            "vin": row[0],
            "license_plate": row[1],
            "brand": row[2],
            "model": row[3],
            "mileage": row[4],
            "fuel_type": row[5],
            "warranty_end_date": row[6],
            "apk_renew_date": row[7],
            "tyres": get_tyre_info(row[0])
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/customer/<customer_id>/vehicles', methods=['GET'])
def get_customer_vehicles(customer_id):
    """
    Get all vehicles for a customer
    Example: /api/customer/00-289739/vehicles
    """
    try:
        result = con.execute(f"""
        SELECT 
            v.vin,
            v.license_plate,
            v.brand_name,
            v.model_name,
            v.mileage
        FROM dim_vehicles v
        JOIN fact_vehicle_ownership fvo ON v.vin = fvo.vehicle_vin
        WHERE fvo.customer_id = ?
        """, [customer_id]).fetchall()
        
        if not result:
            return jsonify({"error": "Customer not found"}), 404
        
        vehicles = [
            {
                "vin": r[0],
                "license_plate": r[1],
                "brand": r[2],
                "model": r[3],
                "mileage": r[4],
                "tyres": get_tyre_info(r[0])
            } for r in result
        ]
        
        return jsonify(vehicles), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/customer/<customer_id>/info', methods=['GET'])
def get_customer_info(customer_id):
    """
    Get customer info + vehicle count
    Example: /api/customer/00-289739/info
    """
    try:
        cust = con.execute(f"""
        SELECT given_name, family_name, address_line1, city, postal_code
        FROM dim_customers
        WHERE customer_id = ?
        """, [customer_id]).fetchall()
        
        if not cust:
            return jsonify({"error": "Customer not found"}), 404
        
        vehicles = con.execute(f"""
        SELECT COUNT(*) FROM fact_vehicle_ownership
        WHERE customer_id = ?
        """, [customer_id]).fetchall()
        
        row = cust[0]
        response = {
            "customer_id": customer_id,
            "given_name": row[0] or "",
            "family_name": row[1] or "",
            "address": f"{row[2] or ''}, {row[3] or ''}",
            "postal_code": row[4] or "",
            "vehicle_count": vehicles[0][0]
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        # Try a simple query
        con.execute("SELECT 1").fetchall()
        return jsonify({"status": "ok", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/vehicle/diagnostic/<plate>', methods=['GET'])
def get_vehicle_diagnostic(plate):
    """
    Complete vehicle diagnostic by license plate
    Returns: customer info, vehicle info, maintenance needs, pricing, duration
    Example: /api/vehicle/diagnostic/GZW-20-W
    """
    plate = plate.upper()
    
    try:
        # Get vehicle + owner
        vehicle_result = con.execute(f"""
        SELECT 
            v.vin,
            v.license_plate,
            v.brand_name,
            v.model_name,
            v.mileage,
            v.fuel_type,
            v.warranty_end_date,
            v.apk_renew_date,
            c.customer_id,
            c.given_name,
            c.family_name,
            c.address_line1,
            c.city,
            c.postal_code
        FROM dim_vehicles v
        LEFT JOIN fact_vehicle_ownership fvo ON v.vin = fvo.vehicle_vin
        LEFT JOIN dim_customers c ON fvo.customer_id = c.customer_id
        WHERE v.license_plate = ?
        LIMIT 1
        """, [plate]).fetchone()
        
        if not vehicle_result:
            return jsonify({"error": "Vehicle not found"}), 404
        
        vin = vehicle_result[0]
        
        # Detect if vehicle is leased
        is_leased = is_vehicle_leased(vin)
        
        # Get last service
        service_result = con.execute(f"""
        SELECT service_date, mileage_km, work_description, dealer_name
        FROM fact_service_history
        WHERE vehicle_vin = ?
        ORDER BY service_date DESC
        LIMIT 1
        """, [vin]).fetchone()
        
        # Get maintenance intervals
        intervals = con.execute(f"""
        SELECT description, interval_months, interval_kilometers
        FROM dim_maintenance_intervals
        WHERE vehicle_vin = ?
        """, [vin]).fetchall()
        
        # Get available PON packages from the VIN-specific JSON file
        # (not from generic database - each VIN has its specific packages!)
        import json
        from pathlib import Path
        
        pon_packages = []
        pon_file = Path(__file__).parent.parent / "ai_werkorder_expert" / "maintenance_packages" / "pon_packages" / f"{vin}.json"
        
        if pon_file.exists():
            try:
                with open(pon_file) as f:
                    data = json.load(f)
                    if data and len(data) > 0:
                        pon_data = data[0].get('pon_packages', {})
                        if isinstance(pon_data, dict):
                            for pon in pon_data.get('pon', []):
                                category_name = pon.get('name', 'Unknown')
                                category_code = pon.get('code', '00')
                                
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
                                    
                                    # Check if ORU/OTA (Owner's task)
                                    is_owner_task = 'OTA' in child.get('name', '') or 'ORU' in child.get('name', '')
                                    
                                    # Store as dictionary with ALL details
                                    pon_packages.append({
                                        "code": child.get('code', f"PON_{len(pon_packages)}"),
                                        "name": child.get('name', ''),
                                        "description": child.get('description', ''),
                                        "type": child.get('type', 'PON'),
                                        "duration_hours": allowed_time,
                                        "price_incl": float(price_incl) if price_incl else None,
                                        "price_excl": float(price_excl) if price_excl else None,
                                        "duration_category": duration,
                                        "category": category_name,
                                        "category_code": category_code,
                                        "is_owner_task": is_owner_task,
                                        "contents": child.get('contents', []),  # All line items
                                        "prices": child.get('prices', []),  # All price variants (lease/no-lease)
                                    })
            except Exception as e:
                pass  # If file doesn't exist or parsing fails, continue with empty packages
        
        # Deduplicate by NAME - keep only first occurrence of each service
        seen_names = {}
        deduped_packages = []
        for p in pon_packages:
            name = (p.get('name', "") or "").strip()
            if name not in seen_names:
                seen_names[name] = True
                deduped_packages.append(p)
        pon_packages = deduped_packages
        
        # Get recalls for this vehicle
        recalls = con.execute(f"""
        SELECT recall_id, recall_source, status
        FROM fact_recalls
        WHERE vehicle_vin = ?
        """, [vin]).fetchall()
        
        # Calculate maintenance needs
        current_mileage = vehicle_result[4]
        last_service_date = service_result[0] if service_result else None
        last_service_km = service_result[1] if service_result else 0
        
        maintenance_needed = []
        
        # Check APK
        apk_date = vehicle_result[7]
        apk_days = days_until_date(apk_date) if apk_date else None
        if apk_days is not None and apk_days <= 30:
            # Find matching APK package
            apk_pkg = find_package_for_maintenance("APK", pon_packages)
            # Apply correct pricing based on lease status
            if apk_pkg:
                apk_pkg = apply_lease_pricing_to_package(apk_pkg, is_leased)
            
            maintenance_needed.append({
                "type": "APK",
                "urgency": "HIGH" if apk_days <= 0 else "MEDIUM",
                "date": apk_date,
                "days_remaining": apk_days,
                "duration_hours": apk_pkg["duration_hours"] if apk_pkg else 0.4,
                "price_incl": apk_pkg["price_incl"] if apk_pkg else 50.0,
                "price_excl": apk_pkg["price_excl"] if apk_pkg else 41.32,
                "package": apk_pkg  # Entire package object with all details!
            })
        
        # Check warranty
        warranty_end = vehicle_result[6]
        warranty_days = days_until_date(warranty_end) if warranty_end else None
        warranty_valid = warranty_days is not None and warranty_days > 0
        
        # Estimate maintenance from intervals
        km_since_service = current_mileage - last_service_km if last_service_km else current_mileage
        
        for interval in intervals:
            desc, months, km = interval
            if km and km_since_service >= km * 0.8:  # 80% of interval = high urgency
                # Determine urgency based on how overdue
                if km_since_service >= km:
                    urgency = "HIGH"
                elif km_since_service >= km * 0.9:
                    urgency = "MEDIUM"
                else:
                    urgency = "LOW"
                
                # Find matching package for this maintenance type
                maint_pkg = find_package_for_maintenance(desc, pon_packages)
                # Apply correct pricing based on lease status
                if maint_pkg:
                    maint_pkg = apply_lease_pricing_to_package(maint_pkg, is_leased)
                
                maintenance_needed.append({
                    "type": desc,
                    "urgency": urgency,
                    "interval_km": km,
                    "km_since_service": km_since_service,
                    "km_overdue": km_since_service - km,
                    "duration_hours": maint_pkg["duration_hours"] if maint_pkg else 1.0,
                    "price_incl": maint_pkg["price_incl"] if maint_pkg else 100.0,
                    "price_excl": maint_pkg["price_excl"] if maint_pkg else 82.64,
                    "package": maint_pkg  # Entire package object with all details!
                })
        
        response = {
            "vehicle": {
                "vin": vin,
                "license_plate": vehicle_result[1],
                "brand": vehicle_result[2],
                "model": vehicle_result[3],
                "mileage_km": current_mileage,
                "fuel_type": vehicle_result[5],
                "is_leased": is_leased,
                "tyres": get_tyre_info(vin),
                "warranty": {
                    "end_date": warranty_end,
                    "days_remaining": warranty_days,
                    "is_valid": warranty_valid
                },
                "apk": {
                    "renew_date": apk_date,
                    "days_remaining": apk_days
                }
            },
            "owner": {
                "customer_id": vehicle_result[8],
                "name": f"{vehicle_result[9] or ''} {vehicle_result[10] or ''}".strip(),
                "address": f"{vehicle_result[11] or ''}, {vehicle_result[12] or ''}",
                "postal_code": vehicle_result[13]
            },
            "last_service": {
                "date": service_result[0] if service_result else None,
                "mileage_km": service_result[1] if service_result else None,
                "work": service_result[2] if service_result else None,
                "dealer": service_result[3] if service_result else None
            },
            # ═══════════════════════════════════════════════════════════
            # MAINTENANCE STATUS
            # ═══════════════════════════════════════════════════════════
            "maintenance_required": len(maintenance_needed) > 0,
            "required_maintenance": [
                {
                    "type": m["type"],
                    "urgency": m["urgency"],
                    "details": {
                        "interval_km": m.get("interval_km"),
                        "km_since_service": m.get("km_since_service"),
                        "km_overdue": m.get("km_overdue"),
                        "days_remaining": m.get("days_remaining"),
                        "date": m.get("date")
                    },
                    "duration_hours": m.get("duration_hours", 0),
                    "estimated_cost": {
                        "price_incl": m.get("price_incl", 0),
                        "price_excl": m.get("price_excl", 0)
                    },
                    "package": m.get("package")  # FULL PACKAGE OBJECT with code, name, description, contents, prices!
                } for m in maintenance_needed
            ],
            "required_maintenance_summary": {
                "total_cost_incl": sum(m.get("price_incl", 0) or 0 for m in maintenance_needed),
                "total_cost_excl": sum(m.get("price_excl", 0) or 0 for m in maintenance_needed),
                "total_duration_hours": sum(m.get("duration_hours", 0) for m in maintenance_needed),
                "count": len(maintenance_needed)
            },
            # ═══════════════════════════════════════════════════════════
            # RECALLS
            # ═══════════════════════════════════════════════════════════
            "recalls": [
                {
                    "id": r[0],
                    "source": r[1],
                    "status": r[2]
                } for r in recalls
            ],
            # ═══════════════════════════════════════════════════════════
            # AVAILABLE MAINTENANCE PACKAGES (for optional work)
            # Grouped by duration category with full package details
            # ═══════════════════════════════════════════════════════════
            "available_packages": {
                "≤2 uur": {
                    "regular": [
                        {
                            "code": p.get("code"),
                            "name": p.get("name"),
                            "description": p.get("description"),
                            "type": p.get("type"),
                            "duration_hours": p.get("duration_hours"),
                            "price_incl": p.get("price_incl"),
                            "price_excl": p.get("price_excl"),
                            "category": p.get("category"),
                            "category_code": p.get("category_code"),
                            "contents": p.get("contents", []),
                            "prices": p.get("prices", [])
                        } for p in pon_packages if p and p.get("duration_category") == "≤2 uur" and not p.get("is_owner_task")
                    ],
                    "owner_tasks": [
                        {
                            "code": p.get("code"),
                            "name": p.get("name"),
                            "description": p.get("description"),
                            "type": p.get("type"),
                            "duration_hours": p.get("duration_hours"),
                            "price_incl": p.get("price_incl"),
                            "price_excl": p.get("price_excl"),
                            "category": p.get("category"),
                            "category_code": p.get("category_code"),
                            "contents": p.get("contents", []),
                            "prices": p.get("prices", []),
                            "note": "ORU/OTA - Owner Repair Unit / Owner Task - executed by owner, not in workshop"
                        } for p in pon_packages if p and p.get("duration_category") == "≤2 uur" and p.get("is_owner_task")
                    ]
                },
                "1 werkdag": {
                    "regular": [
                        {
                            "code": p.get("code"),
                            "name": p.get("name"),
                            "description": p.get("description"),
                            "type": p.get("type"),
                            "duration_hours": p.get("duration_hours"),
                            "price_incl": p.get("price_incl"),
                            "price_excl": p.get("price_excl"),
                            "category": p.get("category"),
                            "category_code": p.get("category_code"),
                            "contents": p.get("contents", []),
                            "prices": p.get("prices", [])
                        } for p in pon_packages if p and p.get("duration_category") == "1 werkdag" and not p.get("is_owner_task")
                    ],
                    "owner_tasks": [
                        {
                            "code": p.get("code"),
                            "name": p.get("name"),
                            "description": p.get("description"),
                            "type": p.get("type"),
                            "duration_hours": p.get("duration_hours"),
                            "price_incl": p.get("price_incl"),
                            "price_excl": p.get("price_excl"),
                            "category": p.get("category"),
                            "category_code": p.get("category_code"),
                            "contents": p.get("contents", []),
                            "prices": p.get("prices", []),
                            "note": "ORU/OTA - Owner Repair Unit / Owner Task"
                        } for p in pon_packages if p and p.get("duration_category") == "1 werkdag" and p.get("is_owner_task")
                    ]
                },
                "langer": {
                    "regular": [
                        {
                            "code": p.get("code"),
                            "name": p.get("name"),
                            "description": p.get("description"),
                            "type": p.get("type"),
                            "duration_hours": p.get("duration_hours"),
                            "price_incl": p.get("price_incl"),
                            "price_excl": p.get("price_excl"),
                            "category": p.get("category"),
                            "category_code": p.get("category_code"),
                            "contents": p.get("contents", []),
                            "prices": p.get("prices", [])
                        } for p in pon_packages if p and p.get("duration_category") == "langer" and not p.get("is_owner_task")
                    ],
                    "owner_tasks": [
                        {
                            "code": p.get("code"),
                            "name": p.get("name"),
                            "description": p.get("description"),
                            "type": p.get("type"),
                            "duration_hours": p.get("duration_hours"),
                            "price_incl": p.get("price_incl"),
                            "price_excl": p.get("price_excl"),
                            "category": p.get("category"),
                            "category_code": p.get("category_code"),
                            "contents": p.get("contents", []),
                            "prices": p.get("prices", []),
                            "note": "ORU/OTA - Owner Repair Unit / Owner Task"
                        } for p in pon_packages if p and p.get("duration_category") == "langer" and p.get("is_owner_task")
                    ]
                }
            }
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Werkorder Expert API Server')
    parser.add_argument('--port', type=int, default=5000, help='Port to run Flask on (default: 5000)')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    args = parser.parse_args()
    
    print("="*60)
    print("🚗 WERKORDER EXPERT - API SERVER")
    print("="*60)
    print(f"Database: {DB_PATH}")
    print(f"Server:   http://{args.host}:{args.port}")
    print(f"Swagger:  http://{args.host}:{args.port}/swagger")
    print("\n📍 API Endpoints:")
    print("  GET /api/vehicle/diagnostic/{plate}        ← Main endpoint!")
    print("  GET /api/vehicle/by-plate?plate=WDX-90-M")
    print("  GET /api/vehicle/by-vin?vin=WVWZZZAW4RU404624")
    print("  GET /api/customer/{id}/vehicles")
    print("  GET /api/customer/{id}/info")
    print("  GET /api/health")
    print("  GET /swagger                               ← API docs")
    print("\n🚀 Running on http://{}:{}".format(args.host, args.port))
    print("="*60 + "\n")
    
    app.run(debug=False, port=args.port, host=args.host, use_reloader=False)
