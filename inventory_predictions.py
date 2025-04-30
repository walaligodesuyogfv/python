#!/usr/bin/env python
"""
Inventory Predictions for ICTD System
This script processes inventory data from the database and generates predictions
"""
import json
import sys
import os
import sqlite3
import datetime
import random
from datetime import timedelta

def get_db_connection():
    """Connect to the database"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'ictd_inventory.db')
    
    # If db doesn't exist, use sqlite memory for demo purposes
    if not os.path.exists(db_path):
        print("Database file not found. Using in-memory database for demo purposes.", file=sys.stderr)
        return sqlite3.connect(':memory:')
    
    return sqlite3.connect(db_path)

def fetch_inventory_data():
    """Fetch inventory data from the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if inventory table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'")
        if not cursor.fetchone():
            # In demo mode, create a temporary inventory table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY,
                item_code TEXT,
                item_name TEXT,
                brand_model TEXT,
                serial_number TEXT,
                purchase_date TEXT,
                warranty_expiration TEXT,
                condition TEXT,
                location TEXT,
                notes TEXT,
                assigned_to TEXT,
                date_added TEXT
            )
            ''')
            conn.commit()
            return []
        
        # Query inventory items
        cursor.execute('''
        SELECT 
            id, item_code, item_name, brand_model, serial_number, 
            purchase_date, warranty_expiration, condition, location, notes,
            assigned_to
        FROM inventory
        ORDER BY id DESC
        ''')
        
        items = []
        for row in cursor.fetchall():
            item = {
                "id": row[0],
                "item_code": row[1],
                "item_name": row[2],
                "brand_model": row[3],
                "serial_number": row[4],
                "purchase_date": row[5],
                "warranty_expiration": row[6],
                "condition": row[7],
                "location": row[8],
                "notes": row[9],
                "assigned_to": row[10]
            }
            items.append(item)
        
        return items
    
    except Exception as e:
        print(f"Database error: {str(e)}", file=sys.stderr)
        return []
    
    finally:
        conn.close()

def generate_maintenance_predictions(inventory):
    """Generate maintenance predictions based on inventory data"""
    if not inventory:
        return []
        
    maintenance_items = []
    today = datetime.datetime.now()
    
    for item in inventory:
        # Calculate maintenance probability based on multiple factors
        probability = 0
        days_until = random.randint(15, 90)  # Default range
        warranty_expired = False
        warranty_expiring_soon = False
        
        # Factor 1: Item condition
        condition_weights = {
            "New": 5,
            "Good": 20,
            "Fair": 50,
            "Poor": 85
        }
        condition = item.get("condition", "Good")
        probability += condition_weights.get(condition, 20)
        
        # Factor 2: Item age based on purchase date
        purchase_date = item.get("purchase_date")
        age_days = 0
        if purchase_date:
            try:
                purchase_date = datetime.datetime.strptime(purchase_date, "%Y-%m-%d")
                age_days = (today - purchase_date).days
                
                # Age-based probability adjustment
                if age_days > 1095:  # >3 years
                    probability += 40
                    days_until = random.randint(5, 30)
                elif age_days > 730:  # >2 years
                    probability += 25
                    days_until = random.randint(15, 45)
                elif age_days > 365:  # >1 year
                    probability += 10
                    days_until = random.randint(30, 60)
            except (ValueError, TypeError):
                pass
        
        # Factor 3: Warranty expiration
        warranty_expiration = item.get("warranty_expiration")
        warranty_days_left = 0
        if warranty_expiration:
            try:
                warranty_date = datetime.datetime.strptime(warranty_expiration, "%Y-%m-%d")
                warranty_days_left = (warranty_date - today).days
                
                if warranty_days_left < 0:
                    # Already expired
                    warranty_expired = True
                    probability += 20
                    days_until = min(days_until, abs(warranty_days_left) + random.randint(5, 15))
                elif warranty_days_left < 30:
                    # Expiring within 30 days
                    warranty_expiring_soon = True
                    probability += 15
                    days_until = min(days_until, warranty_days_left + random.randint(1, 10))
                elif warranty_days_left < 90:
                    # Expiring within 90 days
                    warranty_expiring_soon = True
                    probability += 10
                    days_until = min(days_until, warranty_days_left + random.randint(15, 30))
            except (ValueError, TypeError):
                pass
        
        # Additional factor: If condition is Poor and warranty is expired, very high priority
        if condition == "Poor" and warranty_expired:
            probability += 30
            days_until = random.randint(1, 7)  # Urgent maintenance needed
        
        # Add some randomness for more natural predictions
        probability = min(95, probability + random.randint(-8, 8))
        
        # Only include items with significant probability
        if probability > 30 or warranty_expired or warranty_expiring_soon or condition == "Poor":
            maintenance_items.append({
                "id": item.get("id"),
                "item_name": item.get("item_name", "Unknown Item"),
                "item_code": item.get("item_code", ""),
                "brand_model": item.get("brand_model", ""),
                "serial_number": item.get("serial_number", ""),
                "condition": condition,
                "probability": probability,
                "days_until": days_until,
                "warranty_expired": warranty_expired,
                "warranty_expiring_soon": warranty_expiring_soon,
                "warranty_days_left": warranty_days_left,
                "age_days": age_days,
                "priority": "Critical" if (condition == "Poor" and warranty_expired) else
                           "High" if probability > 70 else 
                           "Medium" if probability > 50 else "Low"
            })
    
    # Sort by priority (Critical first), then by probability (high to low)
    def sort_key(item):
        priority_values = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        return (priority_values.get(item["priority"], 4), -item["probability"])
    
    maintenance_items.sort(key=sort_key)
    
    # Return top items
    return maintenance_items[:5]

def generate_inventory_suggestions(inventory):
    """Generate inventory suggestions based on current inventory"""
    if not inventory:
        return []
        
    # Categorize inventory items
    categories = {}
    conditions = {}
    locations = {}
    warranty_status = {"expired": 0, "expiring_soon": 0, "valid": 0, "unknown": 0}
    item_ages = {"new": 0, "medium": 0, "old": 0, "unknown": 0}
    
    today = datetime.datetime.now()
    
    for item in inventory:
        # Extract category from item name
        item_name = item.get("item_name", "").lower()
        category = "Other"
        
        # Simple categorization logic
        if any(x in item_name for x in ["laptop", "desktop", "computer"]):
            category = "Computers"
        elif any(x in item_name for x in ["printer", "scanner", "copier"]):
            category = "Printers/Scanners"
        elif any(x in item_name for x in ["router", "switch", "network", "hub"]):
            category = "Networking"
        elif any(x in item_name for x in ["monitor", "display", "screen"]):
            category = "Monitors"
        elif any(x in item_name for x in ["keyboard", "mouse", "webcam", "headset"]):
            category = "Peripherals"
        elif any(x in item_name for x in ["server", "rack", "nas", "storage"]):
            category = "Server Equipment"
        elif any(x in item_name for x in ["ups", "battery", "power"]):
            category = "Power Equipment"
        
        # Count items by category
        categories[category] = categories.get(category, 0) + 1
        
        # Track condition
        item_condition = item.get("condition", "Unknown")
        if item_condition not in conditions:
            conditions[item_condition] = 0
        conditions[item_condition] += 1
        
        # Track location
        item_location = item.get("location", "Unknown")
        if item_location not in locations:
            locations[item_location] = 0
        locations[item_location] += 1
        
        # Track warranty status
        warranty_expiration = item.get("warranty_expiration")
        if warranty_expiration:
            try:
                warranty_date = datetime.datetime.strptime(warranty_expiration, "%Y-%m-%d")
                warranty_days_left = (warranty_date - today).days
                
                if warranty_days_left < 0:
                    warranty_status["expired"] += 1
                elif warranty_days_left < 90:
                    warranty_status["expiring_soon"] += 1
                else:
                    warranty_status["valid"] += 1
            except (ValueError, TypeError):
                warranty_status["unknown"] += 1
        else:
            warranty_status["unknown"] += 1
            
        # Track item age
        purchase_date = item.get("purchase_date")
        if purchase_date:
            try:
                purchase_date = datetime.datetime.strptime(purchase_date, "%Y-%m-%d")
                age_days = (today - purchase_date).days
                
                if age_days < 180:  # < 6 months
                    item_ages["new"] += 1
                elif age_days < 730:  # < 2 years
                    item_ages["medium"] += 1
                else:  # >= 2 years
                    item_ages["old"] += 1
            except (ValueError, TypeError):
                item_ages["unknown"] += 1
        else:
            item_ages["unknown"] += 1
    
    # Generate suggestions
    suggestions = []
    
    # Category-based suggestions
    for category, count in categories.items():
        action = "Maintain"
        reason = "Current inventory level is optimal"
        confidence = random.randint(70, 85)
        specific_recommendation = ""
        
        # Simple logic for suggestions
        if count < 2:
            action = "Increase"
            reason = "Low inventory level"
            confidence = random.randint(85, 95)
            specific_recommendation = f"Consider adding at least {3 - count} more {category.lower()} to maintain appropriate reserves"
        elif count > 10:
            action = "Optimize"
            reason = "Potential excess inventory"
            confidence = random.randint(75, 90)
            specific_recommendation = f"Consider redistributing or repurposing excess {category.lower()}"
        else:
            specific_recommendation = f"Current {category.lower()} inventory levels are appropriate"
        
        suggestions.append({
            "category": category,
            "current_count": count,
            "action": action,
            "reason": reason,
            "specific_recommendation": specific_recommendation,
            "confidence": confidence
        })
    
    # Condition-based suggestions
    poor_count = conditions.get("Poor", 0)
    if poor_count > 0:
        suggestions.append({
            "category": "Equipment Maintenance",
            "current_count": poor_count,
            "action": "Replace",
            "reason": f"{poor_count} items in poor condition",
            "specific_recommendation": f"Schedule maintenance or replacement for {poor_count} items in poor condition",
            "confidence": random.randint(85, 95)
        })
    
    # Add warranty-based suggestions
    if warranty_status["expired"] > 0:
        suggestions.append({
            "category": "Warranty Management",
            "current_count": warranty_status["expired"],
            "action": "Renew",
            "reason": f"{warranty_status['expired']} items with expired warranty",
            "specific_recommendation": f"Evaluate renewal options for {warranty_status['expired']} items with expired warranty",
            "confidence": random.randint(80, 95)
        })
    
    if warranty_status["expiring_soon"] > 0:
        suggestions.append({
            "category": "Warranty Planning",
            "current_count": warranty_status["expiring_soon"],
            "action": "Plan",
            "reason": f"{warranty_status['expiring_soon']} items with warranty expiring soon",
            "specific_recommendation": f"Plan budget for {warranty_status['expiring_soon']} items with warranty expiring in the next 90 days",
            "confidence": random.randint(75, 90)
        })
    
    # Add age-based suggestions
    if item_ages["old"] > 3:
        suggestions.append({
            "category": "Equipment Lifecycle",
            "current_count": item_ages["old"],
            "action": "Evaluate",
            "reason": f"{item_ages['old']} items older than 2 years",
            "specific_recommendation": "Plan replacement cycle for aging equipment to prevent unexpected failures",
            "confidence": random.randint(80, 90)
        })
    
    # Sort by confidence (high to low)
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Return top suggestions
    return suggestions[:6]

def get_new_inventory_items(inventory, days=7):
    """Get recently added inventory items"""
    if not inventory:
        return []
    
    # In a real implementation, we'd query the database for items added in the last X days
    # For now, just return a subset of items as "new"
    new_items = inventory[:min(5, len(inventory))]
    
    # Format the items for display
    formatted_items = []
    for item in new_items:
        formatted_items.append({
            "id": item.get("id"),
            "item_name": item.get("item_name", "Unknown Item"),
            "brand_model": item.get("brand_model", ""),
            "serial_number": item.get("serial_number", ""),
            "assigned_to": item.get("assigned_to", "Unassigned"),
            "condition": item.get("condition", "Unknown"),
            "date_added": datetime.datetime.now().strftime("%Y-%m-%d")  # Placeholder
        })
    
    return formatted_items

def main():
    """Main function to generate and output inventory predictions"""
    # Set content type for JSON output
    print("Content-Type: application/json")
    print()  # Empty line after headers
    
    try:
        # Get inventory data
        inventory = fetch_inventory_data()
        
        # Generate various predictions
        maintenance_predictions = generate_maintenance_predictions(inventory)
        inventory_suggestions = generate_inventory_suggestions(inventory)
        new_items = get_new_inventory_items(inventory)
        
        # Compile all predictions into a single response
        predictions = {
            "ml_predictions": {
                "maintenance_predictions": maintenance_predictions,
                "inventory_suggestions": inventory_suggestions,
                "new_inventory_items": new_items,
                "inventory_health": random.randint(65, 95)  # Overall health score
            },
            "success": True,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Output as JSON
        print(json.dumps(predictions, indent=2))
        
    except Exception as e:
        # Return error message if something goes wrong
        error_response = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        print(json.dumps(error_response, indent=2))

if __name__ == "__main__":
    main() 