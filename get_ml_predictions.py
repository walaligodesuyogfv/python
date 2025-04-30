#!/usr/bin/env python3
"""
ML Predictions for Admin Dashboard
This script generates ML predictions for maintenance and inventory suggestions
"""

import sys
import json
import os
from inventory_ml_predictions import fetch_inventory_data, generate_maintenance_predictions, generate_inventory_suggestions, generate_ml_predictions

def main():
    """Generate and return ML predictions"""
    # Set content type header for JSON output
    print("Content-Type: application/json")
    print()  # Empty line to separate headers from content
    
    try:
        # Get prediction type from query parameters if available
        prediction_type = "all"
        if len(sys.argv) > 1:
            prediction_type = sys.argv[1]
        
        if prediction_type == "maintenance":
            # Get only maintenance predictions
            inventory_data = fetch_inventory_data()
            predictions = generate_maintenance_predictions(inventory_data)
            print(json.dumps({
                "success": True,
                "data": predictions
            }))
        elif prediction_type == "inventory":
            # Get only inventory suggestions
            inventory_data = fetch_inventory_data()
            suggestions = generate_inventory_suggestions(inventory_data)
            print(json.dumps({
                "success": True,
                "data": suggestions
            }))
        else:
            # Get all predictions
            predictions = generate_ml_predictions()
            print(json.dumps({
                "success": True,
                "data": predictions
            }))
    except Exception as e:
        # Return error message
        print(json.dumps({
            "success": False,
            "error": str(e)
        }))

if __name__ == "__main__":
    main() 