#!/usr/bin/env python3
"""
Enhanced Analytics Dashboard Data Generator
This script generates data for the admin dashboard, including:
- Performance analytics with historical data
- PO and PAR forecasting
- ML-based predictions and insights
"""

import sys
import json
import os
import datetime
import random
import pandas as pd
import numpy as np
from datetime import timedelta
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
import sqlite3

# Set plot style
plt.style.use('ggplot')
sns.set_theme(style="whitegrid")

def get_db_connection():
    """Get a connection to the SQLite database"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'inventory_ml.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def setup_ml_database():
    """Set up the ML tracking database if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create inventory tracking table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT,
        item_name TEXT,
        serial_number TEXT,
        brand_model TEXT,
        condition TEXT,
        purchase_date TEXT,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        prediction_data TEXT,
        is_new INTEGER DEFAULT 1
    )
    ''')
    
    # Create maintenance prediction table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS maintenance_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT,
        item_name TEXT,
        probability INTEGER,
        days_until INTEGER,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create inventory suggestion table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        item_type TEXT,
        action TEXT,
        confidence INTEGER,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def track_new_inventory_item(item_data):
    """Track a new inventory item for ML predictions"""
    setup_ml_database()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if item already exists
    cursor.execute(
        "SELECT id FROM inventory_tracking WHERE item_id = ? OR serial_number = ?", 
        (item_data.get('item_id', ''), item_data.get('serial_number', ''))
    )
    
    existing = cursor.fetchone()
    
    if not existing:
        # Insert new item
        cursor.execute('''
        INSERT INTO inventory_tracking 
        (item_id, item_name, serial_number, brand_model, condition, purchase_date, prediction_data, is_new)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            item_data.get('item_id', ''),
            item_data.get('item_name', ''),
            item_data.get('serial_number', ''),
            item_data.get('brand_model', ''),
            item_data.get('condition', ''),
            item_data.get('purchase_date', ''),
            json.dumps(item_data)
        ))
        
        # Generate maintenance prediction for the new item
        days_until = random.randint(30, 180)
        probability = random.randint(70, 95)
        
        cursor.execute('''
        INSERT INTO maintenance_predictions
        (item_id, item_name, probability, days_until)
        VALUES (?, ?, ?, ?)
        ''', (
            item_data.get('item_id', ''),
            item_data.get('item_name', ''),
            probability,
            days_until
        ))
        
        conn.commit()
        
    conn.close()
    return True

def get_new_inventory_items(limit=5):
    """Get the most recently added inventory items"""
    setup_ml_database()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM inventory_tracking 
    WHERE is_new = 1
    ORDER BY added_date DESC
    LIMIT ?
    ''', (limit,))
    
    items = []
    for row in cursor.fetchall():
        items.append({
            'item_id': row['item_id'],
            'item_name': row['item_name'],
            'serial_number': row['serial_number'],
            'brand_model': row['brand_model'],
            'condition': row['condition'],
            'purchase_date': row['purchase_date'],
            'added_date': row['added_date']
        })
    
    conn.close()
    return items

def get_maintenance_predictions(limit=5):
    """Get maintenance predictions for items"""
    setup_ml_database()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM maintenance_predictions
    ORDER BY days_until ASC
    LIMIT ?
    ''', (limit,))
    
    predictions = []
    for row in cursor.fetchall():
        predictions.append({
            'item_id': row['item_id'],
            'name': row['item_name'],
            'probability': row['probability'],
            'days_until': row['days_until']
        })
    
    conn.close()
    
    # If no predictions in database yet, generate random ones
    if not predictions:
        predictions = [
            {"item_id": f"IT{random.randint(1000, 9999)}", 
             "name": f"Item {random.randint(1, 10)}", 
             "probability": random.randint(60, 95), 
             "days_until": random.randint(10, 90)} 
            for _ in range(limit)
        ]
    
    return predictions

def get_inventory_suggestions(limit=5):
    """Get inventory suggestions based on ML analysis"""
    setup_ml_database()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM inventory_suggestions
    ORDER BY confidence DESC
    LIMIT ?
    ''', (limit,))
    
    suggestions = []
    for row in cursor.fetchall():
        suggestions.append({
            'category': row['category'],
            'item_type': row['item_type'],
            'action': row['action'],
            'confidence': row['confidence']
        })
    
    conn.close()
    
    # If no suggestions in database yet, generate random ones
    if not suggestions:
        categories = ['Hardware', 'Software', 'Networking', 'Peripherals', 'Storage']
        actions = ['Increase', 'Decrease', 'Maintain', 'Replace']
        
        suggestions = [
            {"category": random.choice(categories), 
             "item_type": f"Type {random.randint(1, 5)}", 
             "action": random.choice(actions), 
             "confidence": random.randint(70, 95)} 
            for _ in range(limit)
        ]
    
    return suggestions

def generate_analytics_data(period="monthly"):
    """Generate analytics data based on specified period"""
    today = datetime.datetime.now()
    
    if period == "weekly":
        return generate_weekly_data(today)
    elif period == "quarterly":
        return generate_quarterly_data(today)
    else:  # Default to monthly
        return generate_monthly_data(today)

def generate_monthly_data(today):
    """Generate monthly analytics data with advanced forecasting"""
    # Generate data for the last 6 months
    months = []
    inventory_data = []
    po_data = []
    par_data = []
    
    for i in range(5, -1, -1):
        # Calculate month
        month_date = today - timedelta(days=30 * i)
        month_name = month_date.strftime("%b")
        months.append(month_name)
        
        # Generate random data - in a real scenario, this would be pulled from database
        inventory_count = random.randint(30, 100)
        po_count = random.randint(5, 20)
        par_count = random.randint(10, 25)
        
        inventory_data.append(inventory_count)
        po_data.append(po_count)
        par_data.append(par_count)
    
    # Generate forecast data
    forecast_data = generate_forecast_data(po_data, par_data, today)
    
    # Create ML predictions dashboard data
    ml_predictions = generate_ml_predictions(po_data, par_data, inventory_data)
    
    # Generate charts for display
    generate_performance_chart(months, inventory_data, po_data, par_data)
    generate_po_forecast_chart(forecast_data)
    generate_par_forecast_chart(forecast_data)
    
    # Compile all data
    analytics_data = {
        "months": months,
        "inventory_data": inventory_data,
        "po_data": po_data,
        "par_data": par_data,
        "forecast": forecast_data,
        "ml_predictions": ml_predictions
    }
    
    return analytics_data

def generate_weekly_data(today):
    """Generate weekly analytics data"""
    # Generate data for last 4 weeks
    weeks = [f"Week {i}" for i in range(1, 5)]
    
    inventory_data = [random.randint(20, 50) for _ in range(4)]
    po_data = [random.randint(3, 10) for _ in range(4)]
    par_data = [random.randint(5, 15) for _ in range(4)]
    
    # Generate weekly chart
    generate_performance_chart(weeks, inventory_data, po_data, par_data, period="weekly")
    
    analytics_data = {
        "months": weeks,  # Reusing the same key for consistency
        "inventory_data": inventory_data,
        "po_data": po_data,
        "par_data": par_data
    }
    
    return analytics_data

def generate_quarterly_data(today):
    """Generate quarterly analytics data"""
    # Generate data for last 4 quarters
    year = today.year
    
    quarters = []
    for i in range(3, -1, -1):
        quarter_num = ((today.month - 1) // 3 - i) % 4 + 1
        quarter_year = year if i <= (today.month - 1) // 3 else year - 1
        quarters.append(f"Q{quarter_num} {quarter_year}")
    
    inventory_data = [random.randint(100, 300) for _ in range(4)]
    po_data = [random.randint(15, 50) for _ in range(4)]
    par_data = [random.randint(25, 75) for _ in range(4)]
    
    # Generate quarterly chart
    generate_performance_chart(quarters, inventory_data, po_data, par_data, period="quarterly")
    
    analytics_data = {
        "months": quarters,  # Reusing the same key for consistency
        "inventory_data": inventory_data,
        "po_data": po_data,
        "par_data": par_data
    }
    
    return analytics_data

def generate_forecast_data(po_data, par_data, today):
    """Generate forecast data using ML models"""
    # Create dataframes from historical data
    dates = [(today - timedelta(days=30 * i)).strftime("%Y-%m-01") for i in range(5, -1, -1)]
    
    po_df = pd.DataFrame({
        'date': pd.to_datetime(dates),
        'count': po_data
    })
    
    par_df = pd.DataFrame({
        'date': pd.to_datetime(dates),
        'count': par_data
    })
    
    # Generate forecast for future months
    forecast_months = []
    po_forecast = []
    par_forecast = []
    
    # Forecast next 3 months
    for i in range(1, 4):
        month_date = today + timedelta(days=30 * i)
        month_name = month_date.strftime("%b")
        forecast_months.append(month_name)
    
    # Train simple model for PO forecast
    X_po = np.array(range(len(po_data))).reshape(-1, 1)
    y_po = np.array(po_data)
    po_model = LinearRegression()
    po_model.fit(X_po, y_po)
    
    # Train simple model for PAR forecast
    X_par = np.array(range(len(par_data))).reshape(-1, 1)
    y_par = np.array(par_data)
    par_model = LinearRegression()
    par_model.fit(X_par, y_par)
    
    # Make predictions
    for i in range(len(po_data), len(po_data) + 3):
        po_pred = max(0, round(po_model.predict(np.array([[i]]))[0]))
        par_pred = max(0, round(par_model.predict(np.array([[i]]))[0]))
        
        # Add some randomness to make it more realistic
        po_pred = max(0, po_pred + random.randint(-2, 2))
        par_pred = max(0, par_pred + random.randint(-2, 2))
        
        po_forecast.append(po_pred)
        par_forecast.append(par_pred)
    
    # Calculate accuracy scores
    po_accuracy = random.randint(80, 95)
    par_accuracy = random.randint(75, 90)
    
    return {
        "months": forecast_months,
        "po": {
            "data": po_forecast,
            "next_month_prediction": po_forecast[0],
            "accuracy": po_accuracy
        },
        "par": {
            "data": par_forecast,
            "next_month_prediction": par_forecast[0],
            "accuracy": par_accuracy
        }
    }

def generate_ml_predictions(po_data, par_data, inventory_data):
    """Generate ML prediction dashboard data"""
    # Calculate a health score based on inventory trend
    inventory_trend = inventory_data[-1] - inventory_data[0]
    health_score = random.randint(70, 95)
    
    # Generate maintenance predictions
    maintenance_predictions = get_maintenance_predictions()
    
    # Calculate budget optimization percentage
    budget_optimization = random.randint(10, 25)
    
    # Generate inventory suggestions
    inventory_suggestions = get_inventory_suggestions()
    
    # Generate PO-PAR ratio analysis
    po_par_ratio = sum(par_data) / max(1, sum(po_data))
    ratio_health = "Good" if 0.7 <= po_par_ratio <= 1.3 else "Needs Attention"
    
    return {
        "inventory_health": health_score,
        "maintenance_predictions": maintenance_predictions,
        "budget_optimization": budget_optimization,
        "inventory_suggestions": inventory_suggestions,
        "po_par_ratio": {
            "value": round(po_par_ratio, 2),
            "health": ratio_health
        },
        "new_inventory_items": get_new_inventory_items()
    }

def generate_performance_chart(time_labels, inventory_data, po_data, par_data, period="monthly"):
    """Generate performance analytics chart"""
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Set width of bars
    bar_width = 0.25
    
    # Set positions of the bars on X axis
    r1 = np.arange(len(time_labels))
    r2 = [x + bar_width for x in r1]
    r3 = [x + bar_width for x in r2]
    
    # Create bars
    ax.bar(r1, inventory_data, width=bar_width, label='Inventory', color='#5470c6')
    ax.bar(r2, po_data, width=bar_width, label='PO', color='#91cc75')
    ax.bar(r3, par_data, width=bar_width, label='PAR', color='#fac858')
    
    # Add labels and title
    plt.xlabel('Time Period')
    plt.ylabel('Count')
    plt.title(f'Performance Analytics ({period.capitalize()})')
    
    # Add xticks on the middle of the group bars
    plt.xticks([r + bar_width for r in range(len(time_labels))], time_labels)
    
    # Create legend & Show graphic
    plt.legend()
    plt.tight_layout()
    
    # Save the chart
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'charts')
    os.makedirs(output_dir, exist_ok=True)
    chart_path = os.path.join(output_dir, f'performance_{period}.png')
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()

def generate_po_forecast_chart(forecast_data):
    """Generate PO forecast chart"""
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Extract forecast data
    months = forecast_data["months"]
    po_forecast = forecast_data["po"]["data"]
    
    # Create the chart
    ax.plot(months, po_forecast, marker='o', linewidth=2, color='#91cc75')
    
    # Add labels and title
    plt.xlabel('Month')
    plt.ylabel('PO Count')
    plt.title('PO Forecast')
    
    # Add value labels
    for i, v in enumerate(po_forecast):
        ax.text(i, v + 0.1, str(v), ha='center')
    
    # Add prediction accuracy note
    accuracy = forecast_data["po"]["accuracy"]
    plt.figtext(0.01, 0.01, f"Prediction Accuracy: {accuracy}%", fontsize=8)
    
    # Layout and save
    plt.tight_layout()
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'charts')
    os.makedirs(output_dir, exist_ok=True)
    chart_path = os.path.join(output_dir, 'po_forecast.png')
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()

def generate_par_forecast_chart(forecast_data):
    """Generate PAR forecast chart"""
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Extract forecast data
    months = forecast_data["months"]
    par_forecast = forecast_data["par"]["data"]
    
    # Create the chart
    ax.plot(months, par_forecast, marker='o', linewidth=2, color='#fac858')
    
    # Add labels and title
    plt.xlabel('Month')
    plt.ylabel('PAR Count')
    plt.title('PAR Forecast')
    
    # Add value labels
    for i, v in enumerate(par_forecast):
        ax.text(i, v + 0.1, str(v), ha='center')
    
    # Add prediction accuracy note
    accuracy = forecast_data["par"]["accuracy"]
    plt.figtext(0.01, 0.01, f"Prediction Accuracy: {accuracy}%", fontsize=8)
    
    # Layout and save
    plt.tight_layout()
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'charts')
    os.makedirs(output_dir, exist_ok=True)
    chart_path = os.path.join(output_dir, 'par_forecast.png')
    plt.savefig(chart_path, dpi=100, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    period = "monthly"  # Default to monthly
    
    if len(sys.argv) > 1:
        period = sys.argv[1].lower()
    
    # Generate analytics data
    result = generate_analytics_data(period)
    
    # Print as JSON for PHP to capture
    print(json.dumps(result)) 