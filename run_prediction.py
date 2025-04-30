#!/usr/bin/env python
"""
Run ML predictions for inventory system on-demand.
This can be used for testing or manual execution.
"""

import sys
import os
import time
import logging
from inventory_predictor import run_predictions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='run_prediction.log'
)
logger = logging.getLogger('run_prediction')

def main():
    """Main function to run predictions"""
    start_time = time.time()
    print("Starting inventory ML predictions...")
    
    try:
        # Run the predictions
        results = run_predictions()
        
        # Log the results summary
        maintenance_count = len(results.get('maintenance', {}).get('predictions', []))
        inventory_count = len(results.get('inventory', {}).get('suggestions', []))
        
        print(f"Generated {maintenance_count} maintenance predictions")
        print(f"Generated {inventory_count} inventory suggestions")
        
        # Check for errors in submission
        maintenance_submission = results.get('submission_results', {}).get('maintenance', {})
        inventory_submission = results.get('submission_results', {}).get('inventory', {})
        
        if 'error' in maintenance_submission:
            print(f"WARNING: Error submitting maintenance predictions: {maintenance_submission['error']}")
        
        if 'error' in inventory_submission:
            print(f"WARNING: Error submitting inventory suggestions: {inventory_submission['error']}")
        
        # Log execution time
        execution_time = time.time() - start_time
        print(f"Execution completed in {execution_time:.2f} seconds")
        
        return 0
    except Exception as e:
        logger.error(f"Error running predictions: {str(e)}")
        print(f"ERROR: Failed to run predictions: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 