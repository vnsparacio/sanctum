"""Local-only immutable snapshots. Filenames and source paths never leave the Mac."""
import base64
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from common import Refused, atomic, canonical, database, digest, private_dir, strict_json


def normalize_image(raw):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 25000000
    with Image.open(io.BytesIO(raw)) as source:
        if source.format not in ['PNG','JPEG','WEBP'] or getattr(source, 'n_frames', 1) != 1: raise Refused('unsupported_image')
        source.load(); im = ImageOps.exif_transpose(source).convert('RGB'); im.thumbnail((768,768))
        out = io.BytesIO(); im.save(out, format='JPEG', quality=75, optimize=True)
    value = out.getvalue()
    if len(value) > 131072: raise Refused('normalized_image_too_large')
    return {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(value).decode()}}


def video_frames(path, cfg):
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Force a bounded container demuxer and disable network protocols even inside
    # media metadata. We never accept playlists or follow user-supplied URLs.
    demuxer = 'mov' if path.suffix.lower() in ['.mp4','.mov'] else 'matroska'
    args = [ffmpeg,'-nostdin','-hide_banner','-protocol_whitelist','file,pipe','-f',demuxer,'-i',str(path)]
    r = subprocess.run(args, capture_output=True, timeout=30)
    match = re.search(rb'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', r.stderr)
    if not match: raise Refused('video_duration_unavailable')
    h,m,s = map(float, match.groups()); duration = h*3600+m*60+s
    if not 0 < duration <= cfg['max_video_seconds']: raise Refused('video_duration_limit')
    count = min(6, cfg['max_images']); times = [round(duration*i/count,3) for i in range(count)]
    frames = []
    for stamp in times:
        args = [ffmpeg,'-nostdin','-v','error','-ss',str(stamp),'-protocol_whitelist','file,pipe','-f',demuxer,'-i',str(path),'-frames:v','1','-an','-vf','scale=768:768:force_original_aspect_ratio=decrease','-f','image2pipe','-vcodec','mjpeg','pipe:1']
        r = subprocess.run(args, capture_output=True, timeout=30)
        if r.returncode or not r.stdout or len(r.stdout)>2000000: raise Refused('video_frame_failed')
        frames.append(normalize_image(r.stdout))
    return frames, {'kind':'sampled_video','duration_seconds':duration,'frame_timestamps_seconds':times,'audio_included':False,'continuous_coverage':False}


def prepare(paths, settings, now=time.time):
    if not paths or len(paths)>12: raise Refused('attachment_count_limit')
    cfg = settings['multimodal']; images=[]; documents=[]; observations=[]
    root = private_dir(Path(settings['state_directory'])/'media')
    for raw_path in paths:
        path=Path(raw_path).expanduser()
        if path.is_symlink() or not path.is_file() or path.stat().st_size>cfg['max_file_bytes']: raise Refused('unsafe_or_oversize_file')
        ext=path.suffix.lower()
        if ext in ['.jpg','.jpeg','.png','.webp']:
            images.append(normalize_image(path.read_bytes())); observations.append({'kind':'image'})
        elif ext in ['.mp4','.mov','.webm','.mkv']:
            # Snapshot the bytes before parsing; no source-file changes during extraction.
            with tempfile.TemporaryDirectory(dir=root) as td:
                copied=Path(td)/('input'+ext); shutil.copyfile(path,copied); copied.chmod(0o600)
                frames, observation=video_frames(copied,cfg)
            images.extend(frames); observations.append(observation)
        elif ext in ['.txt','.md','.csv','.json','.py','.js','.mjs','.pdf']:
            if ext=='.pdf':
                from pypdf import PdfReader
                reader=PdfReader(io.BytesIO(path.read_bytes()))
                if reader.is_encrypted or len(reader.pages)>50: raise Refused('pdf_limit_or_encrypted')
                value='\n'.join(page.extract_text() or '' for page in reader.pages)
            else: value=path.read_text(encoding='utf-8')
            if not value.strip() or len(value.encode())>settings['max_context_bytes']: raise Refused('document_text_limit')
            documents.append({'kind':'extracted_text','text':value})
            observations.append({'kind':'document_text','extraction':'text_only_no_embedded_images'})
        else: raise Refused('unsupported_file_type')
    if len(images)>cfg['max_images'] or len(canonical(documents).encode())>settings['max_context_bytes']: raise Refused('attachment_bundle_limit')
    content={'images':images,'documents':documents,'observations':observations}
    token=os.urandom(32).hex()
    packet={'created_at':now(),'content':content,'digest':digest(content),'summary':{'count':len(paths),'visual_count':len(images),'document_count':len(documents),'video_count':sum(x['kind']=='sampled_video' for x in observations)}}
    atomic(root/(token+'.json'),canonical(packet).encode())
    return {'token':token,'digest':packet['digest'],'summary':packet['summary'],'command':'/gate attach '+token}


def load(token, expected, scope, settings, bind=False, now=time.time):
    if type(token) is not str or not re.fullmatch('[a-f0-9]{64}',token): raise Refused('media_token')
    path=Path(settings['state_directory'])/'media'/(token+'.json')
    if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_size>5000000: raise Refused('unsafe_media_snapshot')
    packet=strict_json(path.read_text())
    if digest(packet['content'])!=packet['digest'] or (expected and expected!=packet['digest']): raise Refused('media_changed')
    with database(settings['state_directory']) as c:
        c.execute('create table if not exists media_bindings (token text primary key,scope text)')
        row=c.execute('select scope from media_bindings where token=?',(token,)).fetchone()
        if bind and not row:
            if now()-packet['created_at']>86400: raise Refused('unbound_media_expired')
            c.execute('insert into media_bindings values (?,?)',(token,scope)); row=(scope,)
        if not row or row[0]!=scope: raise Refused('media_scope_mismatch')
    return packet


def expand(packet, scope, settings):
    """Only a signed exact disclosure can contain a media reference."""
    result=dict(packet)
    ref=result.pop('media_ref',None)
    if ref:
        if set(ref)!= {'token','digest'}: raise Refused('media_reference')
        result.update(load(ref['token'],ref['digest'],scope,settings)['content'])
    return result
