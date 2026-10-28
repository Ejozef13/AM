"""Real PDF extraction and bounded lexical retrieval, without model calls."""
import base64
import shutil
import unittest
from note_retrieval import extract_pdf, retrieve


def pdf_bytes(text):
    # Tiny text-based PDF built for extraction verification, not a study question.
    content=f'BT /F1 12 Tf 30 100 Td ({text}) Tj ET'.encode()
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream']
    out=b'%PDF-1.4\n'; offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out)); out+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(out); out+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    out+=b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    return out+f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()


class NotesTests(unittest.TestCase):
    def test_retrieval_finds_late_relevant_material_and_preserves_citations(self):
        notes=('unrelated astronomy observations. '*1000)+'\f'+('Graph traversal uses a queue and visited vertices. '*100)
        context,citations=retrieve('Graph traversal',notes)
        self.assertLessEqual(len(context),10000)
        self.assertIn('Graph traversal',context)
        self.assertTrue(any('2' in row['source'] for row in citations))
        for row in citations: self.assertIn(row['excerpt'],notes)
        with self.assertRaisesRegex(ValueError,'No matching passages'):
            retrieve('neuroscience',notes)

    @unittest.skipUnless(shutil.which('pdftotext'),'Install Poppler for the real PDF probe.')
    def test_text_pdf_extraction(self):
        text=extract_pdf(base64.b64encode(pdf_bytes('Graph traversal visits vertices.')).decode())
        self.assertIn('Graph traversal visits vertices.',text)

    def test_invalid_upload_is_rejected(self):
        for value in ('not base64',base64.b64encode(b'not a pdf').decode(),None):
            with self.assertRaises(ValueError): extract_pdf(value)
