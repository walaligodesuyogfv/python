import sys
import os
import json
import datetime
import pymysql
def get_db_connection():
    """Get database connection to fix dates"""
    try:
        # Direct connection settings
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
        print(f"Error connecting to database: {str(e)}")
        return None

def fix_future_dates():
    """Fix future dates in the database"""
    connection = get_db_connection()
    if not connection:
        return {
            'status': 'error',
            'message': 'Failed to connect to database'
        }
    
    try:
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        with connection.cursor() as cursor:
            # Check for future dates in PO table
            cursor.execute("SELECT COUNT(*) as count FROM purchase_orders WHERE po_date > CURDATE()")
            result = cursor.fetchone()
            po_future_count = result['count'] if result else 0
            
            # Check for future dates in PAR table
            try:
                cursor.execute("SELECT COUNT(*) as count FROM par WHERE date_acquired > CURDATE()")
                result = cursor.fetchone()
                par_future_count = result['count'] if result else 0
            except:
                par_future_count = 0  # Table might not exist
            
            # Update PO dates - use direct SQL with CURDATE()
            cursor.execute("UPDATE purchase_orders SET po_date = CURDATE() WHERE po_date > CURDATE()")
            po_updated = cursor.rowcount
            
            # Update PAR dates if table exists
            par_updated = 0
            try:
                cursor.execute("UPDATE par SET date_acquired = CURDATE() WHERE date_acquired > CURDATE()")
                par_updated = cursor.rowcount
            except:
                pass  # Table might not exist
        
        connection.commit()
        connection.close()
        
        # Detailed report
        result = {
            'status': 'success',
            'message': f'Fixed future dates in the database',
            'po_future_count': po_future_count,
            'par_future_count': par_future_count,
            'po_rows_updated': po_updated,
            'par_rows_updated': par_updated,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return result
        
    except Exception as e:
        if connection:
            connection.close()
        return {
            'status': 'error',
            'message': f'Error fixing dates: {str(e)}'
        }

if __name__ == "__main__":
    # Run the date fix
    result = fix_future_dates()
    print(json.dumps(result, indent=2)) 