"""Bounded local text/PDF extraction and lexical retrieval with source citations."""
import base64
import binascii
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys

MAX_DOCUMENT = 200000


def extract_pdf(encoded):
    if not isinstance(encoded, str) or len(encoded) > 5600000:
        raise ValueError('Choose a PDF below 4 MB.')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Invalid PDF upload.') from None
    if len(data) > 4*1024*1024 or not data.startswith(b'%PDF-'):
        raise ValueError('Choose a PDF below 4 MB.')
    if not shutil.which('pdftotext'):
        raise ValueError('PDF extraction needs Poppler: sudo apt install poppler-utils (Arch: sudo pacman -S poppler).')
    with tempfile.TemporaryDirectory(prefix='am-pdf-') as directory:
        source, output = Path(directory)/'notes.pdf', Path(directory)/'notes.txt'
        source.write_bytes(data)
        try:
            limits = ('import os,resource,sys; '
                      'resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912)); '
                      'resource.setrlimit(resource.RLIMIT_FSIZE,(2097152,2097152)); '
                      'resource.setrlimit(resource.RLIMIT_CPU,(10,10)); '
                      'os.execvp(sys.argv[1],sys.argv[1:])')
            subprocess.run([sys.executable,'-c',limits,shutil.which('pdftotext'),'-f' ,'1','-l','150','-enc','UTF-8',str(source),str(output)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except (subprocess.SubprocessError, OSError):
            raise ValueError('Could not extract this PDF. Try an unencrypted, text-based PDF.') from None
        if output.stat().st_size > 1000000:
            raise ValueError('Extracted PDF is too long; upload a shorter section.')
        text = output.read_text(encoding='utf-8')
    if not text.strip():
        raise ValueError('This PDF contains no extractable text. Scanned PDFs need OCR before upload.')
    if len(text) > MAX_DOCUMENT:
        raise ValueError('Extracted notes exceed 200,000 characters. Upload a shorter section.')
    return text


def retrieve(topic, notes, limit=10000):
    if len(notes) <= limit:
        return notes, [{'source':'Pasted/uploaded notes','excerpt':notes[:600]}] if notes.strip() else []
    terms = set(re.findall(r'[a-z0-9_]{2,}', topic.lower())) - {'the','and','for','with','code','python','java'}
    chunks = []
    offset = 0
    for page_index, page in enumerate(notes.split('\f'), 1):
        for start in range(0,len(page),1000):
            chunk = page[start:start+1000]
            words = re.findall(r'[a-z0-9_]{2,}',chunk.lower())
            score = sum(math.log1p(words.count(term)) for term in terms)
            chunks.append((score,offset+start,page_index,chunk))
        offset += len(page)+1
    if terms and not any(item[0] for item in chunks):
        raise ValueError('No matching passages were found in the long notes. Use a topic mentioned in them or paste a focused excerpt.')
    chosen = sorted(sorted(chunks,key=lambda item:(-item[0],item[1]))[:8],key=lambda item:item[1])
    citations = [{'source':f'Notes page/section {page}, character {start}', 'excerpt':chunk[:600]} for _,start,page,chunk in chosen]
    context = '\n\n'.join(f'[Notes page/section {page}, character {start}]\n{chunk}' for _,start,page,chunk in chosen)
    return context[:limit], citations
