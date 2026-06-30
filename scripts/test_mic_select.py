import os, sys
sys.path.insert(0, os.getcwd())
from audio_processor import create_processor
p = create_processor()
print('Chosen mic_index:', p.mic_index)
print('Done')
