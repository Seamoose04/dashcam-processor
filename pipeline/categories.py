# Processors (mapping categories → functions)
from pipeline.processors.yolo_vehicle import load_vehicle_model, process_vehicle
from pipeline.processors.yolo_plate import load_plate_model, process_plate
from pipeline.processors.ocr import load_ocr, process_ocr
from pipeline.processors.plate_smooth import load_plate_smoother, process_plate_smooth
from pipeline.processors.summary import load_summary, process_summary

from pipeline.task import TaskCategory

gpu_categories = [
    TaskCategory.VEHICLE_DETECT,
    TaskCategory.PLATE_DETECT,
    TaskCategory.OCR
]

cpu_categories = [
    TaskCategory.PLATE_SMOOTH,
    TaskCategory.SUMMARY
]

# -----------------------------------------------------------
# GPU resource loaders / processors
# -----------------------------------------------------------
gpu_resource_loaders = {
    TaskCategory.OCR:            load_ocr,
    TaskCategory.VEHICLE_DETECT: load_vehicle_model,
    TaskCategory.PLATE_DETECT:   load_plate_model,
}

gpu_processors = {
    TaskCategory.OCR:            process_ocr,
    TaskCategory.VEHICLE_DETECT: process_vehicle,
    TaskCategory.PLATE_DETECT:   process_plate,
}

# -----------------------------------------------------------
# CPU resource loaders / processors
# -----------------------------------------------------------
cpu_resource_loaders = {
    TaskCategory.PLATE_SMOOTH: load_plate_smoother,
    TaskCategory.SUMMARY:      load_summary,
}

cpu_processors = {
    TaskCategory.PLATE_SMOOTH: process_plate_smooth,
    TaskCategory.SUMMARY:      process_summary,
}