# Training

## Symlinks

```fish
for f in darknet_dataset/labels/train/*.txt
    ln -s (realpath $f) darknet_dataset/images/train/(basename $f)
end
```

```fish
for f in darknet_dataset/labels/val/*.txt
    ln -s (realpath $f) darknet_dataset/images/val/(basename $f)
end
```

## Acquire Model Checkpoint

```bash
darknet partial ../../yolov7/yolov7.cfg ../../yolov7/yolov7.weights yolov7.conv.143 143
```

## Train

```bash
darknet detector train darknet_dataset/obj.data lpr.cfg yolo.conv.143 -map -dont_show
```
