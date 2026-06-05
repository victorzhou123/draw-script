import os
os.add_dll_directory(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin')
os.add_dll_directory(r'C:\Users\victor\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\nvidia\cudnn\bin')

import sys
print("python:", sys.version)

import cv2
print("cv2 file:", cv2.__file__)
print("cv2 version:", cv2.__version__)
print("cuda count:", cv2.cuda.getCudaEnabledDeviceCount())
