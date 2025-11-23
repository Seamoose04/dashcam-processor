# test_writer.py
from pipeline.writer import get_writer

from dotenv import load_dotenv
load_dotenv()

def main():
    writer = get_writer()
    print("Got writer, attempting insert...")
    writer.write_vehicle(
        video_id="test_video",
        frame_idx=123,
        final_plate="TEST123",
        conf=0.99,
        car_bbox={"x1": 10, "y1": 20, "x2": 100, "y2": 200},
        plate_bbox={"x1": 15, "y1": 25, "x2": 80, "y2": 60},
    )
    print("Insert attempted.")

if __name__ == "__main__":
    main()
