#!/usr/bin/env python3
"""
Database inspection tool - view tables and run queries
"""
import duckdb
import sys
from tabulate import tabulate

# Connect to database
db_path = "backend/hackathon.duckdb"
conn = duckdb.connect(db_path, read_only=True)

def show_tables():
    """List all tables in database"""
    print("\n📊 DATABASE TABLES:")
    print("=" * 60)
    
    result = conn.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()
    
    for i, (table_name,) in enumerate(result, 1):
        # Get row count
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"{i:2}. {table_name:<40} ({row_count:,} rows)")

def show_table_structure(table_name):
    """Show table schema"""
    print(f"\n📋 TABLE: {table_name}")
    print("=" * 60)
    
    result = conn.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """).fetchall()
    
    for i, (col_name, col_type) in enumerate(result, 1):
        print(f"{i:2}. {col_name:<40} {col_type}")

def show_table_sample(table_name, limit=5):
    """Show sample rows from table"""
    print(f"\n📄 SAMPLE DATA ({limit} rows):")
    print("=" * 60)
    
    result = conn.execute(f"SELECT * FROM {table_name} LIMIT {limit}").fetchall()
    columns = [desc[0] for desc in conn.execute(f"SELECT * FROM {table_name} LIMIT 1").description]
    
    print(tabulate(result, headers=columns, tablefmt="grid"))

def query_database(sql):
    """Run custom SQL query"""
    print("\n🔍 QUERY RESULT:")
    print("=" * 60)
    
    try:
        result = conn.execute(sql).fetchall()
        if not result:
            print("(No results)")
            return
        
        # Get column names
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        
        print(tabulate(result, headers=columns, tablefmt="grid"))
        print(f"\n✓ {len(result)} rows returned")
    except Exception as e:
        print(f"❌ Error: {e}")

def stats():
    """Show database statistics"""
    print("\n📈 DATABASE STATISTICS:")
    print("=" * 60)
    
    stats_data = [
        ["Customers (dim_customers)", conn.execute("SELECT COUNT(*) FROM dim_customers").fetchone()[0]],
        ["Vehicles (dim_vehicles)", conn.execute("SELECT COUNT(*) FROM dim_vehicles").fetchone()[0]],
        ["Dealers (dim_dealers)", conn.execute("SELECT COUNT(*) FROM dim_dealers").fetchone()[0] if "dim_dealers" in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()[0] else 0],
        ["Maintenance Intervals", conn.execute("SELECT COUNT(*) FROM dim_maintenance_intervals").fetchone()[0]],
        ["Ownership Links", conn.execute("SELECT COUNT(*) FROM fact_vehicle_ownership").fetchone()[0]],
        ["Service Records", conn.execute("SELECT COUNT(*) FROM fact_service_history").fetchone()[0]],
        ["Repairs", conn.execute("SELECT COUNT(*) FROM fact_repairs").fetchone()[0] if "fact_repairs" in str(conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()) else 0],
        ["Repair Labor", conn.execute("SELECT COUNT(*) FROM fact_repair_labor").fetchone()[0] if "fact_repair_labor" in str(conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()) else 0],
        ["Recalls", conn.execute("SELECT COUNT(*) FROM fact_recalls").fetchone()[0]],
        ["Contracts", conn.execute("SELECT COUNT(*) FROM fact_contracts").fetchone()[0] if "fact_contracts" in str(conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()) else 0],
        ["Vehicle Current State", conn.execute("SELECT COUNT(*) FROM fact_vehicle_current_state").fetchone()[0] if "fact_vehicle_current_state" in str(conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()) else 0],
    ]
    print(tabulate(stats_data, headers=["Entity", "Count"], tablefmt="grid"))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
╔════════════════════════════════════════════════════════════════╗
║         🚗 HACKATHON DATABASE INSPECTION TOOL 🚗              ║
╚════════════════════════════════════════════════════════════════╝

Gebruik:
  python inspect_db.py tables              → Toon alle tabellen
  python inspect_db.py stats               → Database statistieken
  python inspect_db.py schema <table>      → Toon kolommen van tabel
  python inspect_db.py sample <table> [n]  → Toon sample rijen
  python inspect_db.py query "<sql>"       → Voer custom query uit

Voorbeelden:
  python inspect_db.py schema dim_customers
  python inspect_db.py sample fact_service_history 10
  python inspect_db.py query "SELECT brand_name, COUNT(*) FROM dim_vehicles GROUP BY brand_name"
  python inspect_db.py query "SELECT * FROM dim_customers WHERE given_name LIKE '%Bouwe%'"
        """)
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "tables":
        show_tables()
    elif cmd == "stats":
        stats()
    elif cmd == "schema":
        if len(sys.argv) < 3:
            print("❌ Geef tabelnaam op: python inspect_db.py schema <table>")
            sys.exit(1)
        show_table_structure(sys.argv[2])
    elif cmd == "sample":
        if len(sys.argv) < 3:
            print("❌ Geef tabelnaam op: python inspect_db.py sample <table> [n]")
            sys.exit(1)
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        show_table_sample(sys.argv[2], limit)
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("❌ Geef SQL query op: python inspect_db.py query \"SELECT ...\"")
            sys.exit(1)
        query_database(sys.argv[2])
    else:
        print(f"❌ Onbekend commando: {cmd}")
        sys.exit(1)
    
    conn.close()
