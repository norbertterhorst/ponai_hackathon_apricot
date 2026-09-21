# 🚗 AI Werkorder Expert - Hackathon 2026

Complete vehicle diagnostic API with smart maintenance detection, recalls, and service packages for vehicle workshop management.

## 📋 What's Included

- **DuckDB Database** - 623 customers, 1,142 vehicles, 511 recalls, 568 service records
- **Flask REST API** - 7 endpoints including complete diagnostic (werkorder) feature
- **Swagger/OpenAPI** - Auto-generated API documentation
- **Cloudflare Tunnel Ready** - Share with team instantly
- **Multi-user Support** - Colleague can work on port 5001 while you run production on 5000
- **Snowflake Star Schema** - Proper dimensional model with 11 tables

---

## 🤝 Overdracht / Handover

> ⚠️ **Alle data is mockup-data**, gegenereerd voor de hackathon. Er zit geen echte klant- of voertuiginformatie in.

Je hebt de JSON-brondata (`ai_werkorder_expert/`) al. Wat je nodig hebt om verder te gaan:

1. **Pull de laatste versie** (ook de submodule):
   ```bash
   git pull
   git submodule update --init --recursive
   ```
2. **Zet de database op** (bouwt `backend/hackathon.duckdb` opnieuw uit de JSONs, veilig om te herhalen):
   ```bash
   source venv/bin/activate
   python backend/setup_duckdb.py
   ```
3. **Start de DuckDB inspector** (lokale query-pagina, read-only):
   ```bash
   python backend/web_inspect.py
   # open http://localhost:5555
   ```
   Tabblad **🔍 Query** laat je vrij SQL uitvoeren op alle tabellen.

Zie [database-schema.mmd](database-schema.mmd) voor het volledige ER-diagram, en de tabel hieronder voor kolommen per tabel.

### Kolommen per tabel

| Tabel | Kolommen |
|---|---|
| `dim_customers` | customer_id (PK), given_name, family_name, address_line1, address_line2, postal_code, city, country_code, status, language_code |
| `dim_vehicles` | vin (PK), license_plate, brand_name, model_name, model_type, fuel_type, mileage, warranty_end_date, apk_renew_date, first_assigned_date, is_dutch_vehicle |
| `dim_maintenance_intervals` | interval_id (PK), vehicle_vin, description, interval_months, interval_kilometers |
| `dim_dealers` | dealer_id (PK), dealer_name, street, postal_code, city, country, authorization_status |
| `dim_pon_packages` | pon_code (PK), pon_name, pon_description, allowed_time_hours, price_inclusive, price_exclusive, duration_category |
| `fact_vehicle_ownership` | ownership_id (PK), vehicle_vin, customer_id, relationship_type |
| `fact_service_history` | service_id (PK), vehicle_vin, service_date, mileage_km, work_description, dealer_name, service_kind, mobility_guarantee |
| `fact_recalls` | recall_id (PK), vehicle_vin, recall_source, status |
| `fact_repairs` | repair_id (PK), vehicle_vin, invoice_number, order_number, acceptance_date, mileage_km, warranty, is_maintenance *(momenteel leeg)* |
| `fact_repair_labor` | labor_id (PK), repair_id, line_number, description, is_maintenance, amount *(momenteel leeg)* |
| `fact_contracts` | contract_id (PK), vehicle_vin, customer_id, contract_type, start_date, end_date, contract_data *(momenteel leeg)* |
| `fact_vehicle_current_state` | vehicle_vin (PK), current_customer_id, current_mileage, last_service_date, next_service_date, warranty_status, last_appointment_date, updated_at |

---

## 🚀 Quick Start (3 steps)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd "AI Werkorder Expert"
python3 -m venv venv
source venv/bin/activate  # Mac/Linux: or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 2. Start API Server

```bash
python backend/app.py
# Or specify custom port:
python backend/app.py --port 5001
```

### 3. Visit Swagger Docs

Open in browser:
```
http://localhost:5000/swagger
```

---

## ⭐ Main Endpoint: Vehicle Diagnostic

### Complete Diagnostic (⭐ MAIN FEATURE)

```bash
GET /api/vehicle/diagnostic/{plate}
```

**Example:**
```bash
curl "http://localhost:5000/api/vehicle/diagnostic/WDX-90-M" | jq '.'
```

**Response includes:**
```json
{
  "vehicle": {
    "vin": "WVWZZZAW4RU404624",
    "license_plate": "WDX-90-M",
    "brand": "Volkswagen",
    "model": "Polo (6) GP",
    "mileage_km": 75500,
    "warranty_valid": null,
    "apk_renew_days": -1234
  },
  "owner": {
    "customer_id": "00-131620",
    "name": "Empty",
    "address": "...",
    "postal_code": "..."
  },
  "maintenance_required": true,
  "required_maintenance": [
    {
      "type": "Inspectie",
      "urgency": "HIGH",
      "details": {...},
      "duration_hours": 0.5,
      "estimated_cost": 100.0
    },
    {
      "type": "olieservice",
      "urgency": "HIGH",
      "estimated_cost": 100.0
    }
  ],
  "required_maintenance_summary": {
    "total_cost": 200.0,
    "total_duration_hours": 1.5,
    "count": 2
  },
  "recalls": [
    {
      "id": "recall-001",
      "source": "ELSA",
      "status": "OPEN"
    }
  ],
  "available_packages": {
    "≤2 uur": {
      "regular": [
        {
          "code": "DP05A1",
          "name": "APK",
          "category": "01 Services&Checks",
          "category_code": "01",
          "duration_hours": 0.4,
          "price_incl": 50.0,
          "price_excl": 41.32
        }
      ],
      "owner_tasks": [
        {
          "code": "OTA123",
          "name": "OTA - Battery check",
          "note": "ORU/OTA - ausgevoerd door eigenaar",
          "category": "05 Owner Tasks"
        }
      ]
    },
    "1 werkdag": {...},
    "langer": {...}
  }
}
```

---

## 📡 All API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **GET** | `/api/vehicle/diagnostic/{plate}` | ⭐ Complete diagnostic (MAIN) |
| GET | `/api/vehicle/by-plate?plate={plate}` | Vehicle info only |
| GET | `/api/vehicle/by-vin?vin={vin}` | VIN lookup |
| GET | `/api/customer/{id}/info` | Customer details |
| GET | `/api/customer/{id}/vehicles` | All customer vehicles |
| GET | `/api/health` | API status |
| GET | `/swagger` | API documentation |
| GET | `/api/openapi.json` | OpenAPI 3.0 spec |

---

## 👥 Team Collaboration

### You (Main Developer) - Production

```bash
# Terminal 1: Run Flask on port 5000
python backend/app.py

# Terminal 2: Start Cloudflare tunnel
cloudflared tunnel --url http://127.0.0.1:5000/
```

Your tunnel URL is shared with users:
```
https://your-tunnel.trycloudflare.com/api/vehicle/diagnostic/WDX-90-M
```

### Colleague (Feature Developer) - Testing Locally

```bash
# Clone your repo
git clone <your-repo-url>
cd "AI Werkorder Expert"
source venv/bin/activate
pip install -r requirements.txt

# Run on different port (LOCAL ONLY)
python backend/app.py --port 5001

# Test locally: http://localhost:5001/swagger
# NOT accessible via tunnel
```

### Merge Workflow

1. **Colleague:** Create feature branch
   ```bash
   git checkout -b feature/new-endpoints
   # Make changes, test on port 5001
   git push origin feature/new-endpoints
   ```

2. **You:** Review & merge
   ```bash
   git pull
   git checkout feature/new-endpoints
   python backend/app.py  # Test on 5000
   git checkout main
   git merge feature/new-endpoints
   git push
   ```

3. **Users:** Tunnel now shows merged code! ✅

---

## 📊 Test Data

### License Plates (Perfect for Testing)

| Plate | Vehicle | Status | Data |
|-------|---------|--------|------|
| `WDX-90-M` | VW Polo | ⭐ BEST TEST | 2 maintenance, 4 recalls, 76 packages |
| `XSH-81-F` | VW Tiguan | ✅ Good | 2 maintenance, 0 recalls, 62 packages |
| `MXT-72-L` | VW Transporter | ✅ Good | 0 maintenance, 5 recalls, 85 packages |
| `GZW-20-W` | VW Caddy | ⚠️ Basic | 0 maintenance, clean |

### Customer IDs

- `00-114464` - Marloes Buma
- `00-115864` - Twan Van de Mortel
- `00-131620` - (Vehicle owner example)

---

## 🔐 Database Info

- **Type:** DuckDB (columnar, in-memory)
- **File:** `backend/hackathon.duckdb` (~500MB)
- **Access:** Read-only (safe for concurrent access)
- **Tables:** 11 (4 dimensions + 7 facts)
- **Customers:** 623
- **Vehicles:** 1,142
- **Service Records:** 568
- **Recalls:** 511
- **Packages:** ~76 per vehicle (VIN-specific)

### Database Schema

```
Dimensions:
  dim_customers (623)
  dim_vehicles (1,142)
  dim_dealers (49)
  dim_maintenance_intervals (2,139)
  dim_pon_packages (21 aggregated)

Facts:
  fact_vehicle_ownership (849)
  fact_service_history (568)
  fact_recalls (511)
  fact_vehicle_current_state (1,142)
  fact_repairs, fact_repair_labor, fact_contracts (empty)
```

---

## 🛠️ Development

### Directory Structure

```
backend/
  ├─ app.py                   # Main Flask API
  ├─ setup_duckdb.py         # Database initialization
  ├─ inspect_db.py           # CLI inspection tool
  ├─ web_inspect.py          # Web-based DB explorer
  └─ hackathon.duckdb        # Database file

ai_werkorder_expert/
  ├─ customer/               # 623 customer JSONs
  ├─ car/
  │  ├─ vehicle_data/        # 1,142 vehicle JSONs
  │  ├─ vehicle_relations/   # Ownership links
  │  └─ contracts/
  ├─ maintenance_packages/   # VIN-specific packages
  ├─ maintenance_history/    # Service records
  ├─ recalls/                # Recall data
  └─ service_intervals/      # Maintenance schedules

frontend/                    # (Optional) HTML UI
```

### Creating New Endpoints

```python
@app.route('/api/your-endpoint', methods=['GET'])
def your_endpoint():
    """Your endpoint description"""
    try:
        result = con.execute("""
            SELECT * FROM dim_vehicles WHERE mileage > 50000 LIMIT 10
        """).fetchall()
        return jsonify({"vehicles": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
```

### Running Database Tools

```bash
# CLI inspector
python backend/inspect_db.py stats
python backend/inspect_db.py tables
python backend/inspect_db.py sample dim_vehicles 5

# Web inspector (port 5555)
python backend/web_inspect.py
```

---

## 🚀 Deploy to Production

### Cloudflare Tunnel (Already Running)

```bash
cloudflared tunnel --url http://127.0.0.1:5000/
```

Share the generated URL with your team!

### Example Calls from Anywhere

```bash
# Get diagnostic
curl https://your-tunnel.trycloudflare.com/api/vehicle/diagnostic/WDX-90-M

# Via jq for pretty output
curl https://your-tunnel.trycloudflare.com/api/vehicle/diagnostic/WDX-90-M | jq '.'

# Specific fields
curl https://your-tunnel.trycloudflare.com/api/vehicle/diagnostic/WDX-90-M | jq '{
  klant: .owner.name,
  onderhoud: .maintenance_required,
  kosten: .required_maintenance_summary.total_cost,
  recalls: (.recalls | length)
}'
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 5000 already in use | Use `python backend/app.py --port 5001` |
| Database locked | Stop all processes: `pkill -9 python` |
| Import errors | Reinstall: `pip install -r requirements.txt` |
| Flask won't start | Check: `cat /tmp/flask.log` |
| Swagger not loading | Verify: `curl http://localhost:5000/swagger` |
| Tunnel URL not working | Ensure Flask runs on matching port |

---

## 📚 Learning Resources

- **DuckDB:** https://duckdb.org/docs
- **Flask:** https://flask.palletsprojects.com
- **Swagger/OpenAPI:** https://swagger.io/tools/swagger-ui/
- **Cloudflare Tunnel:** https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

---

## ✅ Ready for Hackathon!

- ✅ Database: 623 customers, 1,142 vehicles, 511 recalls
- ✅ API: 8 endpoints with Swagger docs
- ✅ Diagnostic Feature: Smart maintenance detection + recalls + packages
- ✅ Multi-user Support: Read-only DB + port configuration
- ✅ Team Collaboration: Git branches + merge workflow
- ✅ Deployment: Cloudflare tunnel ready

**Start building!** 🚀

---

*AI Werkorder Expert - AI Hackathon 2026*

## 📈 Performance

- Database load time: ~5 seconds
- Query response time: <50ms (indexed)
- Server startup: ~2 seconds
- Memory usage: ~150MB (all data in memory)

---

## 🔄 Workflow for Frontend Team

1. **Backend team** runs setup & API
2. **Frontend team** hits these endpoints:
   - `GET /api/vehicle/by-plate?plate=XXX` ← Main lookup
   - `GET /api/customer/{id}/vehicles` ← Fleet view
   - `GET /api/vehicle/by-vin?vin=XXX` ← VIN lookup

3. **Return format**: JSON with all needed info
4. **No auth required** (yet!)

---

## 🚀 Next Steps

- [ ] Add more endpoints (recalls, repairs, etc)
- [ ] Add filtering/sorting options
- [ ] Add AI advice layer (ChatGPT/Claude)
- [ ] Migrate to PostgreSQL for production
- [ ] Add authentication

---

## 💡 Notes

- DuckDB is **not a server**, it's embedded
- Each Flask process has its own connection
- For production, switch to PostgreSQL
- All data is **read-only during hackathon** (no writes)

Good luck! 🎯
