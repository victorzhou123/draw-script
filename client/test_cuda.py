import os
os.add_dll_directory(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin')
os.add_dll_directory(r'C:\Users\victor\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\nvidia\cudnn\bin')

import sys

# 临时移出 cv2 包，让 importlib 直接找到 cv2.pyd
sys.path.insert(0, r'C:\Users\victor\AppData\Local\Programs\Python\Python311\Lib\site-packages\cv2')
if 'cv2' in sys.modules:
    del sys.modules['cv2']

import cv2
print('cv2 file:', cv2.__file__)
print('cv2 version:', cv2.__version__)
print('cuda count:', cv2.cuda.getCudaEnabledDeviceCount())
