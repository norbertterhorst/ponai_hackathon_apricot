#!/usr/bin/env python3
"""
Web-based DuckDB inspector - open in browser
"""
from flask import Flask, render_template_string, request, jsonify
import duckdb
import json

app = Flask(__name__)
db_path = "backend/hackathon.duckdb"

# Connect with allow_unsigned_extensions to avoid issues
conn = duckdb.connect(db_path, read_only=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>🚗 DuckDB Inspector</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #e6edf3; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1 { margin: 20px 0; color: #58a6ff; }
        .tabs { display: flex; gap: 10px; margin: 20px 0; border-bottom: 1px solid #30363d; }
        .tab { padding: 10px 20px; cursor: pointer; background: #0d1117; border: none; color: #8b949e; }
        .tab.active { color: #58a6ff; border-bottom: 2px solid #58a6ff; }
        .tab:hover { color: #c9d1d9; }
        .content { display: none; }
        .content.active { display: block; }
        .query-box { 
            width: 100%; 
            padding: 10px; 
            margin: 10px 0; 
            background: #161b22; 
            border: 1px solid #30363d;
            color: #e6edf3;
            font-family: 'Courier New', monospace;
            border-radius: 6px;
            min-height: 80px;
        }
        button { 
            padding: 8px 16px; 
            background: #238636; 
            color: white; 
            border: none; 
            border-radius: 6px; 
            cursor: pointer;
            font-weight: 500;
        }
        button:hover { background: #2ea043; }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 20px;
            background: #0d1117;
            border: 1px solid #30363d;
        }
        th { 
            background: #161b22; 
            padding: 12px; 
            text-align: left;
            border: 1px solid #30363d;
            font-weight: 600;
            color: #58a6ff;
        }
        td { 
            padding: 10px 12px; 
            border: 1px solid #30363d;
            word-break: break-word;
        }
        tr:hover { background: #161b22; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat-box { 
            background: #161b22; 
            padding: 15px; 
            border-radius: 6px;
            border: 1px solid #30363d;
        }
        .stat-box h3 { color: #58a6ff; margin-bottom: 5px; }
        .stat-box .number { font-size: 24px; font-weight: bold; color: #3fb950; }
        .error { color: #f85149; background: #161b22; padding: 10px; border-radius: 6px; border-left: 3px solid #f85149; }
        .loading { color: #8b949e; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚗 DuckDB Inspector</h1>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('tables')">📊 Tables</button>
            <button class="tab" onclick="showTab('stats')">📈 Statistics</button>
            <button class="tab" onclick="showTab('query')">🔍 Query</button>
        </div>

        <!-- TABLES TAB -->
        <div id="tables" class="content active">
            <h2>Database Tables</h2>
            <div id="tables-list" class="loading">Loading...</div>
        </div>

        <!-- STATS TAB -->
        <div id="stats" class="content">
            <h2>Database Statistics</h2>
            <div id="stats-content" class="loading">Loading...</div>
        </div>

        <!-- QUERY TAB -->
        <div id="query" class="content">
            <h2>Custom Query</h2>
            <textarea id="query-input" class="query-box" placeholder="SELECT * FROM dim_vehicles LIMIT 10;"></textarea>
            <button onclick="executeQuery()">Execute Query</button>
            <div id="query-result" style="margin-top: 20px;"></div>
        </div>
    </div>

    <script>
        function showTab(tabName) {
            // Hide all
            document.querySelectorAll('.content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            
            // Show selected
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load data
            if (tabName === 'tables') loadTables();
            if (tabName === 'stats') loadStats();
        }

        function loadTables() {
            fetch('/api/tables')
                .then(r => r.json())
                .then(data => {
                    let html = '<table><tr><th>Table Name</th><th>Row Count</th></tr>';
                    data.tables.forEach(t => {
                        html += `<tr><td>${t.name}</td><td>${t.count.toLocaleString()}</td></tr>`;
                    });
                    html += '</table>';
                    document.getElementById('tables-list').innerHTML = html;
                })
                .catch(e => {
                    document.getElementById('tables-list').innerHTML = `<div class="error">Error: ${e.message}</div>`;
                });
        }

        function loadStats() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    let html = '<div class="stats">';
                    Object.entries(data).forEach(([key, value]) => {
                        html += `<div class="stat-box"><h3>${key}</h3><div class="number">${value.toLocaleString()}</div></div>`;
                    });
                    html += '</div>';
                    document.getElementById('stats-content').innerHTML = html;
                })
                .catch(e => {
                    document.getElementById('stats-content').innerHTML = `<div class="error">Error: ${e.message}</div>`;
                });
        }

        function executeQuery() {
            const query = document.getElementById('query-input').value;
            if (!query.trim()) {
                alert('Enter a query');
                return;
            }
            
            document.getElementById('query-result').innerHTML = '<div class="loading">Executing...</div>';
            
            fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('query-result').innerHTML = `<div class="error">Error: ${data.error}</div>`;
                    return;
                }
                
                let html = `<p><strong>${data.rows.length}</strong> rows returned</p>`;
                if (data.rows.length === 0) {
                    document.getElementById('query-result').innerHTML = html;
                    return;
                }
                
                const cols = Object.keys(data.rows[0]);
                html += '<table><tr>';
                cols.forEach(col => html += `<th>${col}</th>`);
                html += '</tr>';
                data.rows.forEach(row => {
                    html += '<tr>';
                    cols.forEach(col => html += `<td>${row[col]}</td>`);
                    html += '</tr>';
                });
                html += '</table>';
                document.getElementById('query-result').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('query-result').innerHTML = `<div class="error">Error: ${e.message}</div>`;
            });
        }

        // Load tables on start
        loadTables();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/tables')
def get_tables():
    result = conn.execute("""
        SELECT table_name, count(*) as count
        FROM (
            SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'
        ) t
        GROUP BY table_name
    """).fetchall()
    
    tables = []
    for table_name, _ in result:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        tables.append({"name": table_name, "count": count})
    
    return jsonify({"tables": sorted(tables, key=lambda x: x['name'])})

@app.route('/api/stats')
def get_stats():
    stats = {
        "Customers": conn.execute("SELECT COUNT(*) FROM dim_customers").fetchone()[0],
        "Vehicles": conn.execute("SELECT COUNT(*) FROM dim_vehicles").fetchone()[0],
        "Ownership Links": conn.execute("SELECT COUNT(*) FROM fact_vehicle_ownership").fetchone()[0],
        "Service Records": conn.execute("SELECT COUNT(*) FROM fact_service_history").fetchone()[0],
        "Maintenance Intervals": conn.execute("SELECT COUNT(*) FROM dim_maintenance_intervals").fetchone()[0],
        "Recalls": conn.execute("SELECT COUNT(*) FROM fact_recalls").fetchone()[0],
    }
    return jsonify(stats)

@app.route('/api/query', methods=['POST'])
def run_query():
    data = request.json
    query = data.get('query', '')
    
    try:
        result = conn.execute(query).fetchall()
        cursor = conn.execute(query)
        cols = [desc[0] for desc in cursor.description]
        
        rows = [dict(zip(cols, row)) for row in result]
        return jsonify({"rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    print("\n╔════════════════════════════════════════╗")
    print("║    🚗 DuckDB Web Inspector 🚗        ║")
    print("╚════════════════════════════════════════╝")
    print("\n📍 Open: http://localhost:5555")
    print("\nQuit: Ctrl+C\n")
    app.run(port=5555, debug=False)
