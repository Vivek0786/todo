"""Convert existing Windows coverage.xml references into repo-relative 'todo/..' paths.
Usage: py -3 normalize_coverage.py C:\ict711\gtd\coverage.xml coverage.xml
Safe for Windows or Linux; validates every mapped file exists before writing.
"""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 3:
    raise SystemExit('Usage: python normalize_coverage.py INPUT_XML OUTPUT_XML')
infile, outfile = Path(sys.argv[1]), Path(sys.argv[2])
if not infile.is_file():
    raise SystemExit(f'Missing XML input: {infile}')
root = ET.parse(infile).getroot()
classes = root.findall('.//class')
if not classes:
    raise SystemExit('No coverage classes found; source report is unusable.')

for cls in classes:
    original = cls.get('filename', '').replace('\\','/')
    # Coverage can report a relative filename, todo/file.py or a Windows full path.
    if '/todo/' in original:
        relative = 'todo/' + original.rsplit('/todo/',1)[1]
    elif original.startswith('todo/'):
        relative = original
    elif original and not original.startswith('/') and ':' not in original:
        relative = 'todo/' + original
    else:
        raise SystemExit(f'Cannot map coverage filename: {original!r}')
    if not (Path(__file__).parent / relative).is_file():
        raise SystemExit(f'Source file referenced in coverage not found: {relative} (from {original})')
    cls.set('filename', relative)

# Sonar scanner runs at GitHub repo root; paths are relative to this directory.
sources = root.find('sources')
if sources is None:
    sources = ET.SubElement(root,'sources')
for element in list(sources):
    sources.remove(element)
ET.SubElement(sources,'source').text = '.'
if infile.resolve() == outfile.resolve():
    raise SystemExit('Choose a different output file to protect your original coverage.xml')
ET.ElementTree(root).write(outfile, encoding='utf-8', xml_declaration=True)
print(f'Converted {len(classes)} coverage file paths into {outfile}')
print(f'Source: {infile}; coverage result is unchanged, only path mappings are updated.')
