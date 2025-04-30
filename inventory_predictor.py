import requests
import json
import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='inventory_predictor.log'
)
logger = logging.getLogger('inventory_predictor')

# Base URL for the PHP server
BASE_URL = "http://localhost"  # Change to your server address if needed

class InventoryPredictor:
    def __init__(self):
        self.maintenance_model = None
        self.inventory_model = None
        self.scaler = StandardScaler()
    
    def fetch_inventory_data(self):
        """Fetch inventory data from the PHP server"""
        try:
            response = requests.get(f"{BASE_URL}/get_inventory_data.php")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch inventory data: {response.status_code} - {response.text}")
                return {"error": f"Failed to fetch inventory data: {response.status_code}"}
        except Exception as e:
            logger.error(f"Exception when fetching inventory data: {str(e)}")
            return {"error": str(e)}
    
    def train_maintenance_model(self, data=None):
        """Train a model to predict when maintenance will be needed"""
        try:
            if data is None:
                data = self.fetch_inventory_data()
                
            if "error" in data:
                return {"error": data["error"]}
                
            if len(data) < 5:  # Need enough data to train
                # Use dummy model for now
                self.maintenance_model = "dummy"
                return {"status": "using dummy model", "reason": "insufficient data"}
            
            # Extract features
            features = []
            targets = []
            
            for item in data:
                # Convert condition to numeric value
                condition_map = {"New": 4, "Good": 3, "Fair": 2, "Poor": 1}
                condition = condition_map.get(item.get("condition", "Good"), 3)
                
                # Calculate item age in days
                purchase_date = item.get("purchase_date")
                if purchase_date:
                    try:
                        purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d")
                        days_since_purchase = (datetime.now() - purchase_date).days
                    except:
                        days_since_purchase = 365  # Default to 1 year if date parsing fails
                else:
                    days_since_purchase = 365
                
                # Features: condition, days since purchase, warranty
                warranty_days = 365  # Default 1 year
                if item.get("warranty_expiration"):
                    try:
                        warranty_date = datetime.strptime(item.get("warranty_expiration"), "%Y-%m-%d")
                        warranty_days = (warranty_date - datetime.now()).days
                    except:
                        warranty_days = 365
                
                features.append([condition, days_since_purchase, warranty_days])
                
                # Target: needs maintenance (1) or not (0)
                # Logic: items in poor condition or older items are more likely to need maintenance
                needs_maintenance = 1 if condition <= 2 or days_since_purchase > 730 else 0
                targets.append(needs_maintenance)
            
            # Train model
            X_train, X_test, y_train, y_test = train_test_split(features, targets, test_size=0.2, random_state=42)
            self.maintenance_model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.maintenance_model.fit(X_train, y_train)
            
            # Evaluate model
            y_pred = self.maintenance_model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            return {
                "status": "success", 
                "accuracy": accuracy,
                "model_type": "RandomForestClassifier"
            }
        except Exception as e:
            logger.error(f"Error training maintenance model: {str(e)}")
            self.maintenance_model = "dummy"
            return {"error": str(e), "status": "using dummy model"}
    
    def train_inventory_model(self, data=None):
        """Train a model to suggest inventory needs"""
        try:
            if data is None:
                data = self.fetch_inventory_data()
                
            if "error" in data:
                return {"error": data["error"]}
                
            if len(data) < 5:
                self.inventory_model = "dummy"
                return {"status": "using dummy model", "reason": "insufficient data"}
            
            # Extract features for inventory prediction
            features = []
            targets = []
            
            # Group items by type/category
            item_categories = {}
            for item in data:
                category = item.get("item_name", "").split(" ")[0].lower()  # Simple categorization
                if category not in item_categories:
                    item_categories[category] = []
                item_categories[category].append(item)
            
            # For each category, predict if more items are needed
            for category, items in item_categories.items():
                count = len(items)
                avg_condition = sum([{"New": 4, "Good": 3, "Fair": 2, "Poor": 1}.get(
                    i.get("condition", "Good"), 3) for i in items]) / count if count > 0 else 3
                
                # Features: count of items, average condition
                features.append([count, avg_condition])
                
                # Target: need more inventory (1) or not (0)
                # Logic: if few items or poor average condition, suggest more inventory
                need_more = 1 if count < 3 or avg_condition < 2.5 else 0
                targets.append(need_more)
            
            # Train model if we have enough categories
            if len(features) >= 3:
                X_train, X_test, y_train, y_test = train_test_split(features, targets, test_size=0.2, random_state=42)
                self.inventory_model = RandomForestClassifier(n_estimators=50, random_state=42)
                self.inventory_model.fit(X_train, y_train)
                
                # Evaluate model
                y_pred = self.inventory_model.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred) if len(y_test) > 0 else 0
                
                return {
                    "status": "success", 
                    "accuracy": accuracy,
                    "model_type": "RandomForestClassifier"
                }
            else:
                self.inventory_model = "dummy"
                return {"status": "using dummy model", "reason": "insufficient categories"}
                
        except Exception as e:
            logger.error(f"Error training inventory model: {str(e)}")
            self.inventory_model = "dummy"
            return {"error": str(e), "status": "using dummy model"}
    
    def predict_maintenance(self, inventory_items=None):
        """Predict which items will need maintenance soon"""
        try:
            if self.maintenance_model is None:
                self.train_maintenance_model()
                
            if inventory_items is None:
                inventory_items = self.fetch_inventory_data()
                
            if "error" in inventory_items:
                return {"error": inventory_items["error"]}
            
            predictions = []
            
            # Use dummy model if real model not available
            if self.maintenance_model == "dummy":
                # Create some plausible predictions
                for item in inventory_items[:5]:  # Limit to 5 items for dummy model
                    condition = item.get("condition", "Good")
                    if condition == "Poor" or condition == "Fair":
                        confidence = np.random.uniform(0.7, 0.95)
                        days = np.random.randint(10, 60)
                        predictions.append({
                            "item_id": item.get("item_id", ""),
                            "item_name": item.get("item_name", "Unknown"),
                            "serial_number": item.get("serial_number", ""),
                            "current_condition": condition,
                            "maintenance_needed": True,
                            "confidence": confidence,
                            "estimated_days": days,
                            "priority": "High" if condition == "Poor" else "Medium"
                        })
                
                return {
                    "status": "success",
                    "model_type": "dummy",
                    "predictions": predictions
                }
            
            # Use actual model for predictions
            for item in inventory_items:
                # Get features
                condition_map = {"New": 4, "Good": 3, "Fair": 2, "Poor": 1}
                condition = condition_map.get(item.get("condition", "Good"), 3)
                
                purchase_date = item.get("purchase_date")
                if purchase_date:
                    try:
                        purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d")
                        days_since_purchase = (datetime.now() - purchase_date).days
                    except:
                        days_since_purchase = 365
                else:
                    days_since_purchase = 365
                
                warranty_days = 365
                if item.get("warranty_expiration"):
                    try:
                        warranty_date = datetime.strptime(item.get("warranty_expiration"), "%Y-%m-%d")
                        warranty_days = (warranty_date - datetime.now()).days
                    except:
                        warranty_days = 365
                
                # Make prediction
                features = [[condition, days_since_purchase, warranty_days]]
                needs_maintenance = self.maintenance_model.predict(features)[0]
                confidence = np.max(self.maintenance_model.predict_proba(features)[0])
                
                if needs_maintenance:
                    # Estimate days until maintenance
                    estimated_days = max(10, int(30 * (condition / 4.0)))
                    
                    predictions.append({
                        "item_id": item.get("item_id", ""),
                        "item_name": item.get("item_name", "Unknown"),
                        "serial_number": item.get("serial_number", ""),
                        "current_condition": item.get("condition", "Unknown"),
                        "maintenance_needed": True,
                        "confidence": float(confidence),
                        "estimated_days": estimated_days,
                        "priority": "High" if condition <= 2 else "Medium"
                    })
            
            # Sort by priority
            predictions.sort(key=lambda x: 0 if x["priority"] == "High" else 1)
            
            return {
                "status": "success",
                "model_type": "RandomForestClassifier",
                "predictions": predictions
            }
        except Exception as e:
            logger.error(f"Error predicting maintenance: {str(e)}")
            return {"error": str(e)}
    
    def predict_inventory_needs(self, inventory_items=None):
        """Predict inventory needs based on current items"""
        try:
            if self.inventory_model is None:
                self.train_inventory_model()
                
            if inventory_items is None:
                inventory_items = self.fetch_inventory_data()
                
            if "error" in inventory_items:
                return {"error": inventory_items["error"]}
            
            suggestions = []
            
            # Use dummy model if real model not available
            if self.inventory_model == "dummy":
                # Group items by category (simple grouping by first word)
                categories = {}
                for item in inventory_items:
                    category = item.get("item_name", "").split(" ")[0].lower()
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(item)
                
                # Create suggestions for categories with few items
                for category, items in categories.items():
                    if len(items) < 3:
                        suggestions.append({
                            "category": category.capitalize(),
                            "current_count": len(items),
                            "suggested_count": 5,
                            "confidence": np.random.uniform(0.7, 0.9),
                            "reason": "Low inventory count",
                            "priority": "Medium" if len(items) > 0 else "High"
                        })
                
                # Add a suggestion for items in poor condition
                poor_condition_items = [item for item in inventory_items if item.get("condition") == "Poor"]
                if poor_condition_items:
                    category = poor_condition_items[0].get("item_name", "").split(" ")[0].lower()
                    suggestions.append({
                        "category": category.capitalize(),
                        "current_count": len(poor_condition_items),
                        "suggested_count": len(poor_condition_items) + 2,
                        "confidence": 0.85,
                        "reason": "Items in poor condition need replacement",
                        "priority": "High"
                    })
                
                return {
                    "status": "success",
                    "model_type": "dummy",
                    "suggestions": suggestions
                }
            
            # Use actual model for predictions
            # Group items by category
            categories = {}
            for item in inventory_items:
                category = item.get("item_name", "").split(" ")[0].lower()
                if category not in categories:
                    categories[category] = []
                categories[category].append(item)
            
            for category, items in categories.items():
                count = len(items)
                avg_condition = sum([{"New": 4, "Good": 3, "Fair": 2, "Poor": 1}.get(
                    i.get("condition", "Good"), 3) for i in items]) / count if count > 0 else 3
                
                # Make prediction
                features = [[count, avg_condition]]
                needs_more = self.inventory_model.predict(features)[0]
                confidence = np.max(self.inventory_model.predict_proba(features)[0])
                
                if needs_more:
                    # Calculate suggested count
                    suggested_count = max(5, count + 2)
                    reason = "Low inventory count" if count < 3 else "Items need replacement"
                    priority = "High" if count < 2 or avg_condition < 2 else "Medium"
                    
                    suggestions.append({
                        "category": category.capitalize(),
                        "current_count": count,
                        "suggested_count": suggested_count,
                        "confidence": float(confidence),
                        "reason": reason,
                        "priority": priority
                    })
            
            # Sort by priority
            suggestions.sort(key=lambda x: 0 if x["priority"] == "High" else 1)
            
            return {
                "status": "success",
                "model_type": "RandomForestClassifier",
                "suggestions": suggestions
            }
        except Exception as e:
            logger.error(f"Error predicting inventory needs: {str(e)}")
            return {"error": str(e)}
    
    def submit_prediction_to_server(self, prediction_data, endpoint):
        """Submit prediction results back to PHP server"""
        try:
            headers = {
                'Content-Type': 'application/json',
            }
            
            response = requests.post(
                f"{BASE_URL}/{endpoint}",
                data=json.dumps(prediction_data),
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to submit prediction: {response.status_code} - {response.text}")
                return {"error": f"Failed to submit prediction: {response.status_code}"}
        except Exception as e:
            logger.error(f"Exception when submitting prediction: {str(e)}")
            return {"error": str(e)}


# Main function to run predictions
def run_predictions():
    predictor = InventoryPredictor()
    
    # First train the models
    maintenance_result = predictor.train_maintenance_model()
    inventory_result = predictor.train_inventory_model()
    
    logger.info(f"Maintenance model training: {maintenance_result}")
    logger.info(f"Inventory model training: {inventory_result}")
    
    # Run predictions
    maintenance_predictions = predictor.predict_maintenance()
    inventory_suggestions = predictor.predict_inventory_needs()
    
    # Submit predictions to PHP server
    maintenance_submit = predictor.submit_prediction_to_server(
        maintenance_predictions, 
        "save_maintenance_predictions.php"
    )
    
    inventory_submit = predictor.submit_prediction_to_server(
        inventory_suggestions,
        "save_inventory_suggestions.php"
    )
    
    logger.info(f"Maintenance prediction submission: {maintenance_submit}")
    logger.info(f"Inventory suggestion submission: {inventory_submit}")
    
    return {
        "maintenance": maintenance_predictions,
        "inventory": inventory_suggestions,
        "submission_results": {
            "maintenance": maintenance_submit,
            "inventory": inventory_submit
        }
    }


# Entry point for command line execution
if __name__ == "__main__":
    print("Starting inventory predictions...")
    results = run_predictions()
    print(f"Completed predictions: {len(results.get('maintenance', {}).get('predictions', []))} maintenance predictions")
    print(f"Completed predictions: {len(results.get('inventory', {}).get('suggestions', []))} inventory suggestions")
    print("Done.") 