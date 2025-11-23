# pipeline/processors/summary.py

def load_summary():
    return None

def process_summary(task, resource):
    """
    task.payload:
      {
         'final_plate': 'ABC123',
         'car_bbox': [...],
         'frames': [...],
         ...
      }
    """
    # Just echo summary for now
    return task.payload
