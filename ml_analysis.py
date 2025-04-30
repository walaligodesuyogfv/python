#!/usr/bin/env python3
"""
ML Analysis Script for Dashboard
This script performs advanced ML analysis on inventory data
and provides insights and predictions for the dashboard
"""

import sys
import json
import os
import datetime
import pandas as pd
import numpy as np
from django.db import connection
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

def fetch_historical_data():
    """Fetch historical PO and PAR data using Django's database connection"""
    try:
        # Monthly PO data
        po_query = """
            SELECT 
                DATE_FORMAT(po_date, '%Y-%m-01') as month_date,
                COUNT(*) as count 
            FROM purchase_orders 
            WHERE po_date IS NOT NULL 
            GROUP BY DATE_FORMAT(po_date, '%Y-%m') 
            ORDER BY month_date ASC
        """
        
        # Monthly PAR data
        par_query = """
            SELECT 
                DATE_FORMAT(date_acquired, '%Y-%m-01') as month_date,
                COUNT(*) as count 
            FROM property_acknowledgment_receipts 
            WHERE date_acquired IS NOT NULL 
            GROUP BY DATE_FORMAT(date_acquired, '%Y-%m') 
            ORDER BY month_date ASC
        """
        
        # Inventory status data
        inventory_query = """
            SELECT 
                condition,
                COUNT(*) as count
            FROM inventory_items
            GROUP BY condition
        """
        
        with connection.cursor() as cursor:
            # Execute PO query
            cursor.execute(po_query)
            po_result = cursor.fetchall()
            
            # Execute PAR query
            cursor.execute(par_query)
            par_result = cursor.fetchall()
            
            # Execute inventory query
            try:
                cursor.execute(inventory_query)
                inventory_result = cursor.fetchall()
            except:
                inventory_result = []
        
        # Process results for PO data
        po_data = [{'month_date': row[0], 'count': row[1]} for row in po_result]
        po_df = pd.DataFrame(po_data)
        
        # Process results for PAR data
        par_data = [{'month_date': row[0], 'count': row[1]} for row in par_result]
        par_df = pd.DataFrame(par_data)
        
        if not po_data or not par_data:
            return None, None, None
        
        # Convert to proper DataFrames
        po_df['month_date'] = pd.to_datetime(po_df['month_date'])
        po_df.set_index('month_date', inplace=True)
        
        par_df['month_date'] = pd.to_datetime(par_df['month_date'])
        par_df.set_index('month_date', inplace=True)
        
        # Process inventory data
        if inventory_result:
            inventory_data = [{'condition': row[0], 'count': row[1]} for row in inventory_result]
            inventory_df = pd.DataFrame(inventory_data)
        else:
            inventory_df = None
        
        return po_df, par_df, inventory_df
    
    except Exception as e:
        print(f"Error fetching historical data: {str(e)}", file=sys.stderr)
        return None, None, None

def generate_quarterly_predictions(po_df, par_df):
    """Generate predictions for the next quarter"""
    if po_df is None or par_df is None or len(po_df) < 3 or len(par_df) < 3:
        return 0, 0, 0, 0, 0, 0, 0
    
    try:
        # Prepare data - resample to monthly if needed and fill gaps
        date_range = pd.date_range(start=min(po_df.index.min(), par_df.index.min()),
                                  end=max(po_df.index.max(), par_df.index.max()),
                                  freq='MS')
        
        # Reindex and fill missing values
        po_df = po_df.reindex(date_range).fillna(0)
        par_df = par_df.reindex(date_range).fillna(0)
        
        # Calculate the correlation between PO and PAR counts
        correlation = po_df['count'].corr(par_df['count'])
        
        # Create features for both datasets
        def create_features(df):
            df_features = df.copy()
            
            # Basic time features
            df_features['month'] = df_features.index.month
            df_features['year'] = df_features.index.year
            df_features['quarter'] = df_features.index.quarter
            
            # Lag features
            for i in range(1, min(4, len(df_features))):
                df_features[f'lag_{i}'] = df_features['count'].shift(i)
            
            # Rolling statistics
            for window in [3, 6]:
                if len(df_features) > window:
                    df_features[f'rolling_mean_{window}'] = df_features['count'].rolling(window=window).mean()
            
            # Add trend
            df_features['trend'] = np.arange(len(df_features))
            
            return df_features.dropna()
        
        # Create features
        po_features = create_features(po_df)
        par_features = create_features(par_df)
        
        # Train PO model
        X_po = po_features.drop('count', axis=1)
        y_po = po_features['count']
        
        # Train PAR model
        X_par = par_features.drop('count', axis=1)
        y_par = par_features['count']
        
        # Split data into train/test sets if enough data points are available
        if len(X_po) > 10:  # Only split if we have enough data
            X_po_train, X_po_test, y_po_train, y_po_test = train_test_split(X_po, y_po, test_size=0.2, shuffle=False)
            X_par_train, X_par_test, y_par_train, y_par_test = train_test_split(X_par, y_par, test_size=0.2, shuffle=False)
            
            # Use Random Forest for better prediction
            po_model = RandomForestRegressor(n_estimators=100, random_state=42)
            par_model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            # Train models with training data
            po_model.fit(X_po_train, y_po_train)
            par_model.fit(X_par_train, y_par_train)
            
            # Calculate accuracy on test data
            po_test_pred = po_model.predict(X_po_test)
            par_test_pred = par_model.predict(X_par_test)
            
            po_accuracy = r2_score(y_po_test, po_test_pred)
            par_accuracy = r2_score(y_par_test, par_test_pred)
            
            # Calculate MAE for more comprehensive error metrics
            po_mae = mean_absolute_error(y_po_test, po_test_pred)
            par_mae = mean_absolute_error(y_par_test, par_test_pred)
            
            # Retrain on all data for prediction
            po_model.fit(X_po, y_po)
            par_model.fit(X_par, y_par)
        else:
            # Use Random Forest for better prediction
            po_model = RandomForestRegressor(n_estimators=100, random_state=42)
            par_model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            # Train models with all data
            po_model.fit(X_po, y_po)
            par_model.fit(X_par, y_par)
            
            # Calculate accuracy on training data
            po_train_pred = po_model.predict(X_po)
            par_train_pred = par_model.predict(X_par)
            
            po_accuracy = r2_score(y_po, po_train_pred)
            par_accuracy = r2_score(y_par, par_train_pred)
            
            # Calculate MAE for more comprehensive error metrics
            po_mae = mean_absolute_error(y_po, po_train_pred)
            par_mae = mean_absolute_error(y_par, par_train_pred)
        
        # Generate next 3 months dates
        last_date = max(po_features.index.max(), par_features.index.max())
        future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=3, freq='MS')
        
        # Prepare future features
        future_po = pd.DataFrame(index=future_dates)
        future_po['month'] = future_po.index.month
        future_po['year'] = future_po.index.year
        future_po['quarter'] = future_po.index.quarter
        future_po['trend'] = np.arange(len(po_features), len(po_features) + len(future_po))
        
        future_par = pd.DataFrame(index=future_dates)
        future_par['month'] = future_par.index.month
        future_par['year'] = future_par.index.year
        future_par['quarter'] = future_par.index.quarter
        future_par['trend'] = np.arange(len(par_features), len(par_features) + len(future_par))
        
        # Add lag features using historical data
        for i in range(1, min(4, len(po_features))):
            future_po[f'lag_{i}'] = po_features['count'].iloc[-i]
            
        for i in range(1, min(4, len(par_features))):
            future_par[f'lag_{i}'] = par_features['count'].iloc[-i]
        
        # Add rolling mean
        for window in [3, 6]:
            if len(po_features) > window:
                future_po[f'rolling_mean_{window}'] = po_features['count'].iloc[-window:].mean()
                
            if len(par_features) > window:
                future_par[f'rolling_mean_{window}'] = par_features['count'].iloc[-window:].mean()
        
        # Make predictions
        po_predictions = po_model.predict(future_po[X_po.columns])
        par_predictions = par_model.predict(future_par[X_par.columns])
        
        # Sum up for quarterly prediction
        po_next_quarter = round(sum(po_predictions))
        par_next_quarter = round(sum(par_predictions))
        
        return po_next_quarter, par_next_quarter, po_accuracy, par_accuracy, correlation, po_mae, par_mae
    
    except Exception as e:
        print(f"Error generating predictions: {str(e)}", file=sys.stderr)
        return 0, 0, 0, 0, 0, 0, 0

def generate_suggestions(po_df, par_df, inventory_df, po_par_ratio, correlation):
    """Generate AI-powered suggestions based on data analysis"""
    suggestions = []
    
    try:
        # Check if we have enough data
        if po_df is None or par_df is None or len(po_df) < 3 or len(par_df) < 3:
            suggestions.append("Collect more data for more accurate predictions and insights.")
            suggestions.append("Consider setting up regular data entry practices for better forecasting.")
            return suggestions
        
        # Analyze PO/PAR ratio
        if po_par_ratio > 1.2:
            suggestions.append(f"PAR count exceeds PO count by {round((po_par_ratio - 1) * 100)}%. Review inventory sourcing practices.")
        elif po_par_ratio < 0.8:
            suggestions.append("PO count significantly exceeds PAR count. Optimize your procurement to distribution workflow.")
        else:
            suggestions.append("PO to PAR ratio is well-balanced, indicating efficient inventory flow.")
        
        # Analyze correlation
        if correlation > 0.8:
            suggestions.append("Strong correlation between PO and PAR activities suggests synchronized operations.")
        elif correlation < 0.4:
            suggestions.append("Weak correlation between PO and PAR activities. Consider improving coordination.")
        
        # Analyze recent trends
        recent_po = po_df['count'].iloc[-3:].mean()
        overall_po = po_df['count'].mean()
        
        recent_par = par_df['count'].iloc[-3:].mean()
        overall_par = par_df['count'].mean()
        
        if recent_po > overall_po * 1.2:
            suggestions.append("Recent PO activity is higher than average. Prepare for increased inventory management needs.")
        elif recent_po < overall_po * 0.8:
            suggestions.append("Recent PO activity is lower than average. Consider reviewing procurement processes.")
            
        if recent_par > overall_par * 1.2:
            suggestions.append("Recent PAR activity is higher than average. Monitor distribution processes carefully.")
        elif recent_par < overall_par * 0.8:
            suggestions.append("Recent PAR activity is lower than average. Evaluate item distribution workflow.")
        
        # Seasonality check
        if len(po_df) >= 12:
            this_month = datetime.datetime.now().month
            last_year_same_month = po_df[po_df.index.month == this_month]['count'].mean()
            last_3_months = po_df['count'].iloc[-3:].mean()
            
            if last_year_same_month > last_3_months * 1.2:
                suggestions.append("Historical data suggests higher PO activity in this period. Prepare accordingly.")
        
        # Inventory-specific suggestions
        if inventory_df is not None and not inventory_df.empty:
            try:
                # Check conditions distribution
                poor_condition = inventory_df[inventory_df['condition'] == 'Poor']['count'].sum() if 'condition' in inventory_df.columns else 0
                total_items = inventory_df['count'].sum() if 'count' in inventory_df.columns else 0
                
                if total_items > 0 and poor_condition / total_items > 0.2:
                    suggestions.append(f"{round(poor_condition / total_items * 100)}% of inventory items are in poor condition. Consider maintenance or replacement.")
            except:
                pass
        
        # General suggestions if we don't have many specific ones
        if len(suggestions) < 3:
            suggestions.append("Implement barcode scanning for faster inventory processing and better accuracy.")
            suggestions.append("Regular audits can help maintain inventory accuracy and improve data quality.")
            suggestions.append("Consider setting up automatic alerts for items nearing warranty expiration.")
        
        return suggestions
    
    except Exception as e:
        print(f"Error generating suggestions: {str(e)}", file=sys.stderr)
        suggestions.append("Error analyzing data. Please check system logs.")
        return suggestions

def calculate_po_par_ratio(po_df, par_df):
    """Calculate the ratio between PO and PAR counts"""
    if po_df is None or par_df is None or len(po_df) == 0 or len(par_df) == 0:
        return 0
    
    try:
        total_po = po_df['count'].sum()
        total_par = par_df['count'].sum()
        
        if total_po == 0:
            return 0
        
        return total_par / total_po
    
    except Exception as e:
        print(f"Error calculating ratio: {str(e)}", file=sys.stderr)
        return 0

def main():
    """Main function to generate ML analysis"""
    try:
        # Fetch data
        po_df, par_df, inventory_df = fetch_historical_data()
        
        # Calculate metrics
        po_par_ratio = calculate_po_par_ratio(po_df, par_df)
        
        # Generate predictions
        po_next_quarter, par_next_quarter, po_accuracy, par_accuracy, correlation, po_mae, par_mae = generate_quarterly_predictions(po_df, par_df)
        
        # Generate suggestions
        suggestions = generate_suggestions(po_df, par_df, inventory_df, po_par_ratio, correlation)
        
        # Build response
        response = {
            'po_par_ratio': round(po_par_ratio, 2),
            'po_accuracy': max(0, min(1, po_accuracy)),  # Ensure between 0 and 1
            'par_accuracy': max(0, min(1, par_accuracy)),
            'po_mae': round(po_mae, 2),
            'par_mae': round(par_mae, 2),
            'correlation_score': max(-1, min(1, correlation)),  # Ensure between -1 and 1
            'next_quarter_prediction': {
                'po': po_next_quarter,
                'par': par_next_quarter
            },
            'suggestions': suggestions
        }
        
        # Output JSON
        print(json.dumps(response))
    
    except Exception as e:
        print(json.dumps({
            'error': str(e),
            'po_par_ratio': 0,
            'po_accuracy': 0,
            'par_accuracy': 0,
            'po_mae': 0,
            'par_mae': 0,
            'correlation_score': 0,
            'next_quarter_prediction': {'po': 0, 'par': 0},
            'suggestions': ["Error processing data. Please check system logs."]
        }))
        sys.exit(1)

if __name__ == "__main__":
    main() 