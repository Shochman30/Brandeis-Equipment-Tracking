"""Copy the tracker data from the Claude-hosted artifact into index.html.

Usage: python3 sync/sync_from_artifact.py <artifact.html>

Only the embedded data (<script id="state">) is replaced, so the GitHub
Pages code (browser saving) stays as it is. Image links in the artifact
point at /_blob/<id>; they are rewritten to the .jpg files listed in
sync/blob-map.json. Fields in PRIVATE_KEYS are never published. Exits with code 2 and prints the ids if the artifact
uses images that are not in the map yet.
"""
import json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRIVATE_KEYS = ('trackerUrl',)
STATE_RE = re.compile(r'(<script id="state" type="application/json">)(.*?)(</script>)', re.S)


def main(src):
    art = pathlib.Path(src).read_text(encoding='utf-8')
    state = json.loads(STATE_RE.search(art).group(2))
    blob_map = json.loads((ROOT / 'sync/blob-map.json').read_text())

    missing = set()

    def fix(x):
        if isinstance(x, dict):
            return {k: fix(v) for k, v in x.items()}
        if isinstance(x, list):
            return [fix(v) for v in x]
        if isinstance(x, str) and x.startswith('/_blob/'):
            h = x[len('/_blob/'):]
            if h not in blob_map:
                missing.add(h)
                return x
            return blob_map[h]
        return x

    state = fix(state)
    # Link to the private Claude tracker; keep it off the public site.
    for k in PRIVATE_KEYS:
        state.pop(k, None)
    if missing:
        print('UNMAPPED IMAGES:', ' '.join(sorted(missing)))
        sys.exit(2)

    idx = ROOT / 'index.html'
    html = idx.read_text(encoding='utf-8')
    text = json.dumps(state, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    new = STATE_RE.sub(lambda m: m.group(1) + text + m.group(3), html, count=1)
    if new == html:
        print('NO CHANGES')
        return
    idx.write_text(new, encoding='utf-8')

    readme = ROOT / 'README.md'
    today = datetime.date.today()
    stamp = f'{today:%B} {today.day}, {today.year}'
    readme.write_text(re.sub(r'Snapshot exported [^.]*\.', f'Snapshot exported {stamp}.', readme.read_text()))
    print('UPDATED', state.get('date', ''))


if __name__ == '__main__':
    main(sys.argv[1])
