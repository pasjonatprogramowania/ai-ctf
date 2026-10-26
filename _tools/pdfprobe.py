import re, sys, zlib, collections

path = sys.argv[1]
data = open(path, 'rb').read()
print("size", len(data))
print("header", data[:16])
print("ObjStm count", len(re.findall(rb'/ObjStm', data)))
print("XRef", len(re.findall(rb'/Type\s*/XRef', data)))
print("ToUnicode count", len(re.findall(rb'/ToUnicode', data)))
print("FontFile", collections.Counter(re.findall(rb'/FontFile\d?', data)))
print("Subtype fonts", collections.Counter(re.findall(rb'/Subtype\s*/(\w+)', data)).most_common(12))
print("Filters", collections.Counter(re.findall(rb'/Filter\s*/(\w+)', data)).most_common(10))
print("obj count", len(re.findall(rb'\d+\s+\d+\s+obj', data)))
m = re.search(rb'beginbfchar', data)
print("has bfchar", bool(m))
# sample a ToUnicode stream
for mm in re.finditer(rb'/ToUnicode\s+(\d+)\s+(\d+)\s+R', data):
    print("ToUnicode ref obj", mm.group(1), mm.group(2))
    break
print("streams", len(re.findall(rb'stream\r?\n', data)))
print("producer", re.findall(rb'/Producer\s*\(([^)]{0,80})', data)[:2])
print("title", re.findall(rb'/Title\s*\(([^)]{0,80})', data)[:2])
