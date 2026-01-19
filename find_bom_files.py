import os
import glob

for zap_file in glob.glob("tests/**/*.zap", recursive=True):
    with open(zap_file, 'rb') as f:
        data = f.read(3)
        if data == b'\xef\xbb\xbf':
            print(f"BOM found in: {zap_file}")
