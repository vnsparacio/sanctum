"""Actual offline encoder/decoder integration, using generated synthetic frames."""
import base64
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
import imageio_ffmpeg
from PIL import Image
from test_runtime import settings
from media import prepare, load

class Video(unittest.TestCase):
    def test_synthetic_video_has_timestamped_frames_no_audio(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);root.chmod(0o700);source=root/'synthetic.mp4'
            r=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i','color=c=red:s=64x64:d=2','-pix_fmt','yuv420p',str(source)],capture_output=True,timeout=20)
            self.assertEqual(r.returncode,0)
            s=settings(root);p=prepare([source],s);data=load(p['token'],p['digest'],'a',s,bind=True)
            self.assertEqual(data['summary']['video_count'],1);self.assertEqual(data['summary']['visual_count'],6)
            o=data['content']['observations'][0];self.assertFalse(o['audio_included']);self.assertFalse(o['continuous_coverage']);self.assertEqual(len(o['frame_timestamps_seconds']),6)
            for image in data['content']['images']:
                with Image.open(io.BytesIO(base64.b64decode(image['image_url']['url'].split(',')[1]))) as im:self.assertEqual(im.format,'JPEG');self.assertFalse(im.getexif())
