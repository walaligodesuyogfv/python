#!/usr/bin/env python3
"""
Inventory Tracking
This script tracks inventory data for machine learning prediction and updates analytics
"""

import sys
import json
import os
import sqlite3
import datetime
import random
import numpy as np
from pathlib import Path
from datetime import timedelta

def get_db_connection():
    """Get a connection to the SQLite database"""
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create the database directory if it doesn't exist
    db_dir = os.path.join(script_dir, '..', 'config')
    os.makedirs(db_dir, exist_ok=True)
    
    # Connect to the database
    db_path = os.path.join(db_dir, 'inventory_ml.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def setup_inventory_tracking():
    """Set up the inventory tracking tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create inventory tracking table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT,
        item_name TEXT,
        brand_model TEXT,
        serial_number TEXT,
        purchase_date TEXT,
        condition TEXT,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        prediction_data TEXT
    )
    ''')
    
    # Create inventory monthly stats table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory_monthly_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT,
        year INTEGER,
        count INTEGER,
        updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def track_inventory_data(inventory_data):
    """Track an inventory item for ML predictions"""
    # Setup if needed
    setup_inventory_tracking()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if item already exists with the same serial number
    if inventory_data.get('serial_number'):
        cursor.execute(
            "SELECT id FROM inventory_tracking WHERE serial_number = ?", 
            (inventory_data.get('serial_number', ''),)
        )
        
        existing = cursor.fetchone()
        
        if existing:
            # Item with this serial number already exists
            return False
    
    # Insert new inventory item
    try:
        cursor.execute('''
        INSERT INTO inventory_tracking 
        (item_code, item_name, brand_model, serial_number, purchase_date, condition, prediction_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            inventory_data.get('item_code', ''),
            inventory_data.get('item_name', ''),
            inventory_data.get('brand_model', ''),
            inventory_data.get('serial_number', ''),
            inventory_data.get('purchase_date', ''),
            inventory_data.get('condition', ''),
            json.dumps(inventory_data)
        ))
        
        # Update monthly stats
        today = datetime.datetime.now()
        month = today.strftime('%m')
        year = today.year
        
        # Check if entry for this month/year exists
        cursor.execute(
            "SELECT id, count FROM inventory_monthly_stats WHERE month = ? AND year = ?",
            (month, year)
        )
        
        monthly_stats = cursor.fetchone()
        
        if monthly_stats:
            # Update existing stats
            cursor.execute('''
            UPDATE inventory_monthly_stats
            SET count = ?, updated_date = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (
                monthly_stats['count'] + 1,
                monthly_stats['id']
            ))
        else:
            # Insert new stats
            cursor.execute('''
            INSERT INTO inventory_monthly_stats
            (month, year, count)
            VALUES (?, ?, ?)
            ''', (
                month,
                year,
                1
            ))
        
        conn.commit()
        # Update analytics data file to reflect the changes
        update_analytics_cache()
        return True
    except Exception as e:
        print(f"Error inserting inventory: {str(e)}")
        return False
    finally:
        conn.close()

def get_inventory_stats():
    """Get inventory statistics for the dashboard"""
    setup_inventory_tracking()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get monthly inventory counts for the last 12 months
    cursor.execute('''
    SELECT 
        month, 
        year, 
        count
    FROM inventory_monthly_stats
    ORDER BY year, month
    LIMIT 12
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    # Format the data
    months = []
    counts = []
    
    for row in rows:
        month_name = datetime.datetime(year=int(row['year']), month=int(row['month']), day=1).strftime('%b %Y')
        months.append(month_name)
        counts.append(row['count'])
    
    return {
        'months': months,
        'counts': counts
    }

def update_analytics_cache():
    """Update the analytics cache file to reflect inventory changes"""
    try:
        # Get the directory of this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        analytics_script = os.path.join(script_dir, 'get_analytics_data.py')
        
        # Run the analytics script to update the cache
        if os.path.exists(analytics_script):
            # Run with monthly parameter to update the cache
            os.system(f"python {analytics_script} monthly")
            return True
        return False
    except Exception as e:
        print(f"Error updating analytics cache: {str(e)}")
        return False

def main():
    """Main entry point for the script"""
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'message': 'No data file provided'
        }))
        sys.exit(1)
    
    # Read the input file
    data_file = sys.argv[1]
    if not os.path.exists(data_file):
        print(json.dumps({
            'success': False,
            'message': 'Data file not found'
        }))
        sys.exit(1)
    
    try:
        with open(data_file, 'r') as f:
            inventory_data = json.load(f)
        
        # Track the inventory data
        success = track_inventory_data(inventory_data)
        
        print(json.dumps({
            'success': success,
            'message': 'Inventory data tracked successfully' if success else 'Failed to track inventory data'
        }))
    except Exception as e:
        print(json.dumps({
            'success': False,
            'message': f'Error processing inventory data: {str(e)}'
        }))

if __name__ == "__main__":
    main() 