import xml.etree.ElementTree as ET
from pathlib import Path
import random
import shutil

# Configuration
TRAIN_SPLIT = 0.8  # 80% train, 20% val

# Paths
annotations_dir = Path('../dataset/annotations')
images_dir = Path('../dataset/images')

# Create darknet structure
darknet_root = Path('darknet_dataset')
(darknet_root / 'images' / 'train').mkdir(parents=True, exist_ok=True)
(darknet_root / 'images' / 'val').mkdir(parents=True, exist_ok=True)
(darknet_root / 'labels' / 'train').mkdir(parents=True, exist_ok=True)
(darknet_root / 'labels' / 'val').mkdir(parents=True, exist_ok=True)

def convert_voc_to_yolo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    size = root.find('size')
    img_width = int(size.find('width').text)
    img_height = int(size.find('height').text)
    
    yolo_lines = []
    for obj in root.findall('object'):
        bbox = obj.find('bndbox')
        xmin = int(bbox.find('xmin').text)
        ymin = int(bbox.find('ymin').text)
        xmax = int(bbox.find('xmax').text)
        ymax = int(bbox.find('ymax').text)
        
        # Convert to YOLO format
        x_center = ((xmin + xmax) / 2) / img_width
        y_center = ((ymin + ymax) / 2) / img_height
        width = (xmax - xmin) / img_width
        height = (ymax - ymin) / img_height
        
        yolo_lines.append(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
    
    return yolo_lines

# Get all XML files
xml_files = list(annotations_dir.glob('*.xml'))
random.shuffle(xml_files)

# Split into train/val
split_idx = int(len(xml_files) * TRAIN_SPLIT)
train_files = xml_files[:split_idx]
val_files = xml_files[split_idx:]

train_txt_paths = []
val_txt_paths = []

# Process training set
for xml_file in train_files:
    # Convert annotations
    yolo_lines = convert_voc_to_yolo(xml_file)
    
    # Get corresponding image
    img_name = xml_file.stem + '.png'  # or .jpg - adjust as needed
    img_path = images_dir / img_name
    
    if not img_path.exists():
        # Try .jpg if .png doesn't exist
        img_name = xml_file.stem + '.jpg'
        img_path = images_dir / img_name
    
    if img_path.exists():
        # Copy image
        dst_img = darknet_root / 'images' / 'train' / img_name
        shutil.copy(img_path, dst_img)
        
        # Write label file
        label_file = darknet_root / 'labels' / 'train' / (xml_file.stem + '.txt')
        with open(label_file, 'w') as f:
            f.write('\n'.join(yolo_lines))
        
        train_txt_paths.append(str(dst_img.absolute()))

# Process validation set
for xml_file in val_files:
    yolo_lines = convert_voc_to_yolo(xml_file)
    
    img_name = xml_file.stem + '.png'
    img_path = images_dir / img_name
    
    if not img_path.exists():
        img_name = xml_file.stem + '.jpg'
        img_path = images_dir / img_name
    
    if img_path.exists():
        dst_img = darknet_root / 'images' / 'val' / img_name
        shutil.copy(img_path, dst_img)
        
        label_file = darknet_root / 'labels' / 'val' / (xml_file.stem + '.txt')
        with open(label_file, 'w') as f:
            f.write('\n'.join(yolo_lines))
        
        val_txt_paths.append(str(dst_img.absolute()))

# Write train.txt and val.txt
with open(darknet_root / 'train.txt', 'w') as f:
    f.write('\n'.join(train_txt_paths))

with open(darknet_root / 'val.txt', 'w') as f:
    f.write('\n'.join(val_txt_paths))

# Create obj.data
with open(darknet_root / 'obj.data', 'w') as f:
    f.write(f"classes = 1\n")
    f.write(f"train = {(darknet_root / 'train.txt').absolute()}\n")
    f.write(f"valid = {(darknet_root / 'val.txt').absolute()}\n")
    f.write(f"names = {(darknet_root / 'obj.names').absolute()}\n")
    f.write(f"backup = backup/\n")

# Create obj.names
with open(darknet_root / 'obj.names', 'w') as f:
    f.write("license_plate\n")

print(f"Conversion complete!")
print(f"Training images: {len(train_txt_paths)}")
print(f"Validation images: {len(val_txt_paths)}")
print(f"Dataset ready in: {darknet_root}")