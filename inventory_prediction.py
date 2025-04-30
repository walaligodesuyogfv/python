#!/usr/bin/env python3
"""
Inventory Prediction Script

This script analyzes inventory data patterns and provides recommendations 
about which items should be displayed or highlighted in the inventory dashboard.
"""

import sys
import json
import os
import datetime
import pymysql
import pandas as pd
import numpy as np
from configparser import ConfigParser
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

def get_db_connection():
    """Get database connection from config"""
    try:
        # Locate the config file relative to the PHP root directory
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.ini')
        
        if os.path.exists(config_path):
            config = ConfigParser()
            config.read(config_path)
            
            db_config = {
                'host': config.get('database', 'host'),
                'user': config.get('database', 'user'),
                'password': config.get('database', 'password'),
                'db': config.get('database', 'dbname'),
                'charset': 'utf8mb4',
                'cursorclass': pymysql.cursors.DictCursor
            }
        else:
            # Fallback to hardcoded values if config doesn't exist
            db_config = {
                'host': 'localhost',
                'user': 'root',
                'password': '',
                'db': 'ictd_inventory',
                'charset': 'utf8mb4',
                'cursorclass': pymysql.cursors.DictCursor
            }
        
        connection = pymysql.connect(**db_config)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {str(e)}", file=sys.stderr)
        return None

def fetch_inventory_data():
    """Fetch inventory data for analysis"""
    try:
        connection = get_db_connection()
        if not connection:
            raise Exception("Failed to connect to database")
        
        # Query inventory items with usage and view data
        query = """
            SELECT 
                i.*,
                COALESCE(v.view_count, 0) as view_count,
                COALESCE(u.usage_count, 0) as usage_count,
                DATEDIFF(CURRENT_DATE, i.purchase_date) as age_days,
                CASE
                    WHEN i.warranty_expiration IS NOT NULL THEN 
                        DATEDIFF(i.warranty_expiration, CURRENT_DATE)
                    ELSE 0
                END as days_to_warranty_expiration
            FROM 
                inventory_items i
            LEFT JOIN (
                SELECT item_id, COUNT(*) as view_count 
                FROM item_views 
                WHERE view_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
                GROUP BY item_id
            ) v ON i.id = v.item_id
            LEFT JOIN (
                SELECT item_id, COUNT(*) as usage_count 
                FROM item_usage 
                WHERE usage_date >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
                GROUP BY item_id
            ) u ON i.id = u.item_id
        """
        
        # Check if the views and usage tables exist first
        check_query = """
            SELECT 
                COUNT(*) as table_count
            FROM 
                information_schema.tables
            WHERE 
                table_schema = DATABASE() 
                AND table_name IN ('item_views', 'item_usage')
        """
        
        with connection.cursor() as cursor:
            # Check if tables exist
            cursor.execute(check_query)
            result = cursor.fetchone()
            table_count = result['table_count'] if result else 0
            
            if table_count < 2:
                # Create simplified query without table joins
                simplified_query = """
                    SELECT 
                        *,
                        DATEDIFF(CURRENT_DATE, purchase_date) as age_days,
                        CASE
                            WHEN warranty_expiration IS NOT NULL THEN 
                                DATEDIFF(warranty_expiration, CURRENT_DATE)
                            ELSE 0
                        END as days_to_warranty_expiration
                    FROM 
                        inventory_items
                """
                cursor.execute(simplified_query)
            else:
                cursor.execute(query)
                
            inventory_data = cursor.fetchall()
        
        connection.close()
        
        if not inventory_data:
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(inventory_data)
        
        # Fill NaN values with appropriate defaults
        if 'view_count' not in df.columns:
            df['view_count'] = 0
        if 'usage_count' not in df.columns:
            df['usage_count'] = 0
        
        df['purchase_date'] = pd.to_datetime(df['purchase_date'], errors='coerce')
        df['warranty_expiration'] = pd.to_datetime(df['warranty_expiration'], errors='coerce')
        
        # Fill NaN values
        df['age_days'].fillna(0, inplace=True)
        df['days_to_warranty_expiration'].fillna(0, inplace=True)
        
        return df
    
    except Exception as e:
        print(f"Error fetching inventory data: {str(e)}", file=sys.stderr)
        return None

def analyze_inventory_items(inventory_df):
    """
    Analyze inventory items and predict which ones should be displayed
    based on usage patterns, age, and warranty expiration
    """
    if inventory_df is None or len(inventory_df) == 0:
        return {
            "top_items": [],
            "needs_attention": [],
            "recommendations": []
        }
    
    try:
        # Create features for the model
        features_df = inventory_df.copy()
        
        # Handle non-numeric fields
        for col in ['item_name', 'brand_model', 'serial_number', 'assigned_to', 'location', 'condition', 'notes']:
            if col in features_df.columns:
                features_df[col] = features_df[col].astype(str)
        
        # Basic scoring logic for display priority
        if 'view_count' in features_df.columns and 'usage_count' in features_df.columns:
            # Create a score based on views and usage
            features_df['score'] = (
                features_df['view_count'] * 0.3 + 
                features_df['usage_count'] * 0.7
            )
        else:
            # If no usage metrics, use simpler scoring
            features_df['score'] = 50  # Default score
        
        # Increase score for new items (less than 30 days old)
        if 'age_days' in features_df.columns:
            features_df.loc[features_df['age_days'] < 30, 'score'] += 30
        
        # Increase score for items close to warranty expiration (within 30 days)
        if 'days_to_warranty_expiration' in features_df.columns:
            features_df.loc[(features_df['days_to_warranty_expiration'] > 0) & 
                           (features_df['days_to_warranty_expiration'] < 30), 'score'] += 25
        
        # Increase score for items in 'Poor' condition
        if 'condition' in features_df.columns:
            features_df.loc[features_df['condition'] == 'Poor', 'score'] += 20
        
        # Sort items by score
        top_items = features_df.sort_values('score', ascending=False)
        
        # Get top 10 items to display
        top_items_list = []
        for _, item in top_items.head(10).iterrows():
            item_dict = {
                'id': int(item['id']) if 'id' in item and not pd.isna(item['id']) else 0,
                'item_name': str(item['item_name']) if 'item_name' in item else "Unknown",
                'score': float(item['score']),
                'reason': get_display_reason(item)
            }
            top_items_list.append(item_dict)
        
        # Items needing attention (near warranty expiration, poor condition)
        needs_attention = []
        
        # Check for items with expiring warranty
        if 'days_to_warranty_expiration' in features_df.columns:
            expiring_warranty = features_df[
                (features_df['days_to_warranty_expiration'] > 0) & 
                (features_df['days_to_warranty_expiration'] < 30)
            ]
            
            for _, item in expiring_warranty.iterrows():
                attention_dict = {
                    'id': int(item['id']) if 'id' in item and not pd.isna(item['id']) else 0,
                    'item_name': str(item['item_name']) if 'item_name' in item else "Unknown",
                    'reason': f"Warranty expiring in {int(item['days_to_warranty_expiration'])} days"
                }
                needs_attention.append(attention_dict)
        
        # Check for items in poor condition
        if 'condition' in features_df.columns:
            poor_condition = features_df[features_df['condition'] == 'Poor']
            
            for _, item in poor_condition.iterrows():
                attention_dict = {
                    'id': int(item['id']) if 'id' in item and not pd.isna(item['id']) else 0,
                    'item_name': str(item['item_name']) if 'item_name' in item else "Unknown",
                    'reason': "Item in poor condition, consider replacement"
                }
                if attention_dict not in needs_attention:
                    needs_attention.append(attention_dict)
        
        # Generate general recommendations
        recommendations = generate_recommendations(features_df)
        
        return {
            "top_items": top_items_list,
            "needs_attention": needs_attention,
            "recommendations": recommendations
        }
    
    except Exception as e:
        print(f"Error analyzing inventory: {str(e)}", file=sys.stderr)
        return {
            "top_items": [],
            "needs_attention": [],
            "recommendations": []
        }

def get_display_reason(item):
    """Generate a reason why an item should be displayed"""
    reasons = []
    
    if 'age_days' in item and item['age_days'] < 30:
        reasons.append("Recently added")
    
    if 'days_to_warranty_expiration' in item and 0 < item['days_to_warranty_expiration'] < 30:
        reasons.append("Warranty expiring soon")
    
    if 'condition' in item and item['condition'] == 'Poor':
        reasons.append("Poor condition")
    
    if 'view_count' in item and item['view_count'] > 5:
        reasons.append("Frequently viewed")
    
    if 'usage_count' in item and item['usage_count'] > 5:
        reasons.append("Frequently used")
    
    if not reasons:
        return "Relevant to current inventory"
    
    return ", ".join(reasons)

def generate_recommendations(df):
    """Generate general recommendations based on inventory data"""
    recommendations = []
    
    try:
        # Check for items with expired warranty
        if 'days_to_warranty_expiration' in df.columns:
            expired_count = len(df[df['days_to_warranty_expiration'] < 0])
            if expired_count > 0:
                recommendations.append(f"There are {expired_count} items with expired warranty.")
        
        # Check condition distribution
        if 'condition' in df.columns:
            condition_counts = df['condition'].value_counts()
            poor_count = condition_counts.get('Poor', 0)
            total_count = len(df)
            
            if poor_count > 0 and total_count > 0:
                poor_percentage = (poor_count / total_count) * 100
                if poor_percentage > 10:
                    recommendations.append(f"{poor_count} items ({poor_percentage:.1f}%) are in poor condition. Consider planning for replacements.")
        
        # Age-based recommendations
        if 'age_days' in df.columns:
            old_items = len(df[df['age_days'] > 365*3])  # Older than 3 years
            if old_items > 5:
                recommendations.append(f"{old_items} items are over 3 years old. Consider a technology refresh plan.")
        
        # Location-based recommendations  
        if 'location' in df.columns:
            location_counts = df['location'].value_counts()
            if len(location_counts) > 1:
                highest_location = location_counts.idxmax()
                highest_count = location_counts.max()
                
                if highest_count > 10:
                    recommendations.append(f"{highest_count} items are in '{highest_location}'. Ensure proper space management.")
    
    except Exception as e:
        print(f"Error generating recommendations: {str(e)}", file=sys.stderr)
    
    return recommendations

def main():
    """Main entry point for the script"""
    try:
        # Get command line arguments
        if len(sys.argv) > 1:
            analysis_type = sys.argv[1]
        else:
            analysis_type = "standard"
        
        # Fetch inventory data
        inventory_df = fetch_inventory_data()
        
        if inventory_df is None or len(inventory_df) == 0:
            # Return empty template if no data
            result = {
                "success": False,
                "message": "No inventory data available",
                "top_items": [],
                "needs_attention": [],
                "recommendations": []
            }
        else:
            # Analyze inventory data
            analysis_result = analyze_inventory_items(inventory_df)
            
            result = {
                "success": True,
                "message": "Analysis completed successfully",
                "top_items": analysis_result["top_items"],
                "needs_attention": analysis_result["needs_attention"],
                "recommendations": analysis_result["recommendations"]
            }
        
        # Output JSON result
        print(json.dumps(result, default=str))
        
    except Exception as e:
        error_result = {
            "success": False,
            "message": f"Error: {str(e)}",
            "top_items": [],
            "needs_attention": [],
            "recommendations": []
        }
        print(json.dumps(error_result))

if __name__ == "__main__":
    main() 