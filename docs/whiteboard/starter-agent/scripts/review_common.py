"""Standalone review pages from current artifacts and author-supplied stage notes."""
import base64
import html
import io
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
STAGES = {
    'script': ('脚本审阅稿', ['artifacts/script.json', 'artifacts/script_review.json']),
    'scene': ('场景计划审阅稿', ['artifacts/scene_plan.json', 'artifacts/scene_plan_review.json']),
    'assets': ('素材审阅稿', ['artifacts/asset_manifest.json', 'assets/audio/narration_timeline.json']),
    'edit': ('样片审阅稿', ['validation/edit-report.json', 'scripts/edit_deviations.json']),
    'publish': ('发布审阅稿', ['publish_meta.json', 'artifacts/publish_log.json']),
}
STYLE = '''<style>
:root{color-scheme:light dark;font:16px/1.75 system-ui,sans-serif}body{margin:20px auto;padding:0 16px;max-width:900px}
section{border:1px solid #8886;border-radius:12px;padding:16px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}
img{max-width:100%;height:auto}summary{cursor:pointer}h1,h2{line-height:1.35}
</style>'''


def local_path(value):
    path = (P / value).resolve()
    if not path.is_relative_to(P.resolve()):
        raise ValueError('审阅材料必须位于本项目中：' + value)
    return path


def image_uri(value):
    from PIL import Image
    with Image.open(local_path(value)) as source:
        image = source.convert('RGB')
        image.thumbnail((1200, 1200))
        data = io.BytesIO()
        image.save(data, format='WEBP', quality=82)
    return 'data:image/webp;base64,' + base64.b64encode(data.getvalue()).decode('ascii')


def render(stage):
    title, inputs = STAGES[stage]
    script = json.loads((P / 'artifacts/script.json').read_text(encoding='utf-8'))
    config = json.loads((P / 'scripts/scene_data/reviews.json').read_text(encoding='utf-8'))[stage]
    sections = []
    for value in inputs:
        data = json.loads(local_path(value).read_text(encoding='utf-8'))
        sections.append('<section><h2>' + html.escape(value) + '</h2><details open><summary>本课构建结果</summary><pre>' + html.escape(json.dumps(data, ensure_ascii=False, indent=2)) + '</pre></details></section>')
    for row in config['notes']:
        sections.append('<section><h2>' + html.escape(row['title']) + '</h2><p>' + html.escape(row['text']) + '</p></section>')
    for row in config['images']:
        sections.append('<section><h2>' + html.escape(row['caption']) + '</h2><img alt="' + html.escape(row['caption'], quote=True) + '" src="' + image_uri(row['path']) + '"></section>')
    for value in config['files']:
        file = local_path(value)
        sections.append('<section><p>' + html.escape(value) + ' · ' + str(file.stat().st_size) + ' bytes</p></section>')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title>' + STYLE + '<main><h1>' + html.escape(script['title']) + ' · ' + title + '</h1>' + ''.join(sections) + '</main></html>'
    output = P / 'review' / (title + '.html')
    output.parent.mkdir(exist_ok=True)
    output.write_text(page, encoding='utf-8')
    print(output)
