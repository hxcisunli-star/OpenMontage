"""E139 contracts: lesson 6 figures, honesty, integration and byte preservation."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'docs/whiteboard/ebook'))
import blocks
import build_site
import check_site

FIXTURES = ROOT / 'tests/fixtures/ebook_l6'
EXAMPLES = ROOT / 'tests/fixtures/ebook_l6/example_records.json'      # in the Codex workspace this was out/example_records.json
sys.path.insert(0, str(FIXTURES))
from ebook_l6_examples import examples_from_tables


def records():
    return json.loads(EXAMPLES.read_text(encoding='utf-8'))


def render(rid, data=None):
    return blocks.show({'id': rid}, blocks.Ctx(records() if data is None else data, {}, {}))


def chapter(data):
    """Use the real chapter renderer; isolate unrelated navigation/outline metadata."""
    u = dict(id='test-unit', no=1, title='图形测试', stage_title='测试')
    b = dict(n=1, title='测试')
    ch = dict(sections=[dict(id='figures', title='图', blocks=[{'t': 'show', 'id': rid}
              for rid, r in data.items() if isinstance(r, dict) and r.get('kind')])],
              lesson_title='测试', basic_question='测试', takeaway=[],
              exercises={'items': [], 'intro': [], 'record': ['测试']})
    with patch.multiple(build_site, topbar=lambda *a: '', status_chips=lambda *a: '',
                        prereq_html=lambda *a: '', pager=lambda *a: ''):
        return build_site.chapter_html(u, b, {}, {}, {u['id']: ch}, {},
                                       dict(records=data, claims={}, urls={}), {})[0]


def parsed(output):
    p = check_site.PageParser()
    p.feed(output)
    p.close()
    assert not p.errors, p.errors
    return p


def test_old_outputs_are_byte_identical():
    baseline = json.loads((FIXTURES / 'baseline.json').read_text(encoding='utf-8'))
    sources = {}
    seen = set()
    for item in baseline:
        source = item['source']
        if source not in sources:
            sources[source] = json.loads((ROOT / source).read_text(encoding='utf-8'))
        assert render(item['id'], sources[source]).encode('utf-8') == item['html'].encode('utf-8')
        seen.add(item['kind'])
    assert set(blocks.LESSON3_KINDS) | set(blocks.LESSON4_KINDS) | set(blocks.LESSON5_KINDS) <= seen


def test_old_chapters_and_drawers_are_byte_identical():
    baseline = json.loads((FIXTURES / 'chapter_baseline.json').read_text(encoding='utf-8'))
    for source, output in baseline.items():
        data = json.loads((ROOT / source).read_text(encoding='utf-8'))
        assert chapter(data).encode('utf-8') == output.encode('utf-8'), source


@pytest.mark.parametrize('rid', ['WIN_shice', 'WIN_shiyi', 'TURN_input', 'GRID_classes'])
def test_each_record_renders_and_captions_have_scope_date_and_tag(rid):
    data = records()
    r = data[rid]
    ctx = blocks.Ctx(data, {}, {})
    output = blocks.show({'id': rid}, ctx)
    p = parsed(output)
    cap = check_site.text_of(check_site.first_descendant(p.root, 'figcaption', 'rec'))
    assert r['title'] in output and r['caliber'] in cap
    assert r['date'] is None or r['date'] in cap
    assert ctx.used_records == [rid]
    want, other = ('shice', 'shiyi') if r['honest'] == 'shice' else ('shiyi', 'shice')
    assert f'class="tag tag-{want}"' in output and f'class="tag tag-{other}"' not in output
    if want == 'shice':
        assert '示意' not in check_site.text_of(p.root)
    if r['kind'] == 'turnbars':
        assert r['model'] in cap and f"{r['runs']} 遍" in cap


TEXT_FIELDS = [
    ('WIN_shice', ['title']), ('WIN_shice', ['caliber']), ('WIN_shice', ['note']),
    ('WIN_shice', ['notes', 1, 'text']), ('WIN_shice', ['notes', 1, 'role_cn']),
    ('WIN_shice', ['notes', 1, 'mark']), ('WIN_shice', ['folder', 'label']),
    ('TURN_input', ['title']), ('TURN_input', ['model']), ('TURN_input', ['caliber']),
    ('TURN_input', ['note']), ('GRID_classes', ['title']), ('GRID_classes', ['caliber']),
    ('GRID_classes', ['note']), ('GRID_classes', ['rows', 0, 'label']),
    ('GRID_classes', ['rows', 0, 'model']), ('GRID_classes', ['rows', 0, 'tally', 'short']),
    ('GRID_classes', ['legend', 0, 'text']), ('GRID_classes', ['labeler']),
]


def field_at(data, path):
    for part in path[:-1]:
        data = data[part]
    return data, path[-1]


@pytest.mark.parametrize('rid,path', TEXT_FIELDS)
def test_strings_are_escaped(rid, path):
    data = records()
    parent, key = field_at(data[rid], path)
    parent[key] = 'AI 模型 <b>x</b> & "引号"'
    output = render(rid, data)
    assert '&lt;b&gt;x&lt;/b&gt;' in output and '<b>x</b>' not in output
    assert '&amp;' in output and '&quot;' in output
    parsed(output)


def test_window_states_folder_pin_marks_and_text_version():
    data = records()
    for rid in ('WIN_shice', 'WIN_shiyi'):
        r = data[rid]
        p = parsed(render(rid, data))
        papers = check_site.descendants(p.root, 'div', 'l6-window-paper')
        assert len(papers) == len(r['notes'])
        for note, paper in zip(r['notes'], papers):
            assert 'l6-window-' + note['state'] in paper.attrs['class'].split()
            text = check_site.text_of(paper)
            assert note['role_cn'] in text and note['text'] in text
            if note['mark']:
                assert note['mark'] in text
            if note['state'] == 'torn':
                assert '这一次不在信封里' in text
            if note['state'] == 'missing':
                assert '缺' in text
        assert len(check_site.descendants(p.root, 'i', 'l6-pin')) == sum(n['state'] == 'pinned' for n in r['notes'])
        assert f"撕下的 {r['folder']['count']} 张在这里，没有消失" in check_site.text_of(p.root)
        text = check_site.first_descendant(p.root, 'div', 'l6-window-text')
        sentences = check_site.descendants(text, 'li')
        assert len(sentences) == len(r['notes'])
        for number, (note, sentence) in enumerate(zip(r['notes'], sentences), 1):
            assert f"第 {number} 条，{note['role_cn']}，{blocks.L6_STATES[note['state']]}" in check_site.text_of(sentence)


def test_window_wraps_each_contiguous_kept_group_without_cutting_papers():
    data = records()
    r = data['WIN_shice']
    # Two adjacent kept papers form one group; a torn one splits groups.
    r['notes'] = [dict(role='user', role_cn='用户', text='一张完整纸条', state=s, mark=None)
                  for s in ['kept', 'kept', 'torn', 'kept', 'kept', 'torn']]
    r['folder']['count'] = sum(n['state'] == 'torn' for n in r['notes'])
    p = parsed(render('WIN_shice', data))
    groups = check_site.descendants(p.root, 'div', 'l6-window-frame')
    assert len(groups) == 2
    assert all(len(check_site.descendants(g, 'div', 'l6-window-paper')) == 2 for g in groups)
    assert all('l6-window-frame' not in paper.attrs['class'].split()
               for paper in check_site.descendants(p.root, 'div', 'l6-window-paper'))
    assert all('l6-window-frame' in paper.parent.attrs['class']
               for g in groups for paper in check_site.descendants(g, 'div', 'l6-window-paper'))


def test_window_digit_runs_are_monospace_and_raw_text_stays_intact():
    data = records()
    raw = '取件码是5086，另一个是42；中文“用户” <b>x</b> & &#123; １２。'
    data['WIN_shice']['notes'][1]['text'] = raw
    p = parsed(render('WIN_shice', data))
    paper = check_site.descendants(p.root, 'div', 'l6-window-paper')[1]
    paragraph = check_site.first_descendant(paper, 'p')
    assert check_site.text_of(paragraph) == raw
    codes = check_site.descendants(paragraph, 'code')
    assert [check_site.text_of(c) for c in codes] == re.findall('[0-9]+', raw)
    assert all(re.fullmatch('[0-9]+', check_site.text_of(c)) for c in codes)


@pytest.mark.parametrize('case', ['count', 'missing', 'state', 'pinned_role'])
def test_window_invalid_records_fail_build(case):
    data = records()
    r = data['WIN_shice']
    if case == 'count':
        r['folder']['count'] += 1
    elif case == 'missing':
        next(n for n in r['notes'] if n['state'] == 'kept')['state'] = 'missing'
    elif case == 'state':
        r['notes'][0]['state'] = '<b>x</b>'
    else:
        r['notes'][0]['role'] = 'user'
    with pytest.raises(ValueError):
        render('WIN_shice', data)


def test_window_optional_folder_and_null_sketch_date():
    data = records()
    data['WIN_shiyi']['folder'] = None
    out = render('WIN_shiyi', data)
    assert 'l6-folder' not in out and 'None' not in out and 'null' not in out


def percentages(style):
    return {key: float(value) for key, value in re.findall(r'(left|width):([0-9.]+)%', style)}


def all_plot_values(r):
    values = [turn[k] for turn in r['turns'] for k in ('full', 'trim')]
    if r['plateau'] is not None:
        values.append(r['plateau'])
    if r['cumulative'] is not None:
        values += [r['cumulative'][k] for k in ('full', 'trim')]
    return values


def test_turnbars_shared_scale_and_range_segments_use_endpoints():
    r = records()['TURN_input']
    p = parsed(render('TURN_input'))
    maximum = max(v['hi'] for v in all_plot_values(r))
    values = [turn[k] for turn in r['turns'] for k in ('full', 'trim')]
    values += [r['cumulative'][k] for k in ('full', 'trim')]
    bars = check_site.descendants(p.root, 'div', 'l6-bar-line')
    assert len(bars) == len(values)
    assert max(v['hi'] / maximum * 100 for v in values) == 100
    for value, bar in zip(values, bars):
        solid = check_site.first_descendant(bar, 'i', 'l6-bar-solid')
        assert percentages(solid.attrs['style'])['width'] == pytest.approx(value['lo'] / maximum * 100, abs=1e-6)
        ranges = check_site.descendants(bar, 'i', 'l6-bar-range')
        assert len(ranges) == (value['lo'] < value['hi'])
        if ranges:
            pos = percentages(ranges[0].attrs['style'])
            assert pos['left'] == pytest.approx(value['lo'] / maximum * 100, abs=1e-6)
            assert pos['left'] + pos['width'] == pytest.approx(value['hi'] / maximum * 100, abs=2e-6)
        shown = check_site.first_descendant(bar, 'span', 'l6-bar-value')
        assert check_site.text_of(shown) == value['display']
    assert '整摞' in check_site.text_of(p.root) and '只留六条' in check_site.text_of(p.root)


def test_plateau_starts_at_recorded_turn_and_uses_both_endpoints():
    r = records()['TURN_input']
    p = parsed(render('TURN_input'))
    maximum = max(v['hi'] for v in all_plot_values(r))
    plateau = r['plateau']
    for turn, row in zip(r['turns'], check_site.descendants(p.root, 'section', 'l6-turn')):
        bands = check_site.descendants(row, 'i', 'l6-plateau-band')
        assert len(bands) == (turn['turn'] >= plateau['from_turn'])
        if bands:
            pos = percentages(bands[0].attrs['style'])
            assert pos['left'] == pytest.approx(plateau['lo'] / maximum * 100, abs=1e-6)
            assert pos['left'] + pos['width'] == pytest.approx(plateau['hi'] / maximum * 100, abs=2e-6)
            assert 'l6-bar-trim' in bands[0].parent.parent.attrs['class']
            assert plateau['display'] in check_site.text_of(row)
    cumulative = check_site.first_descendant(p.root, 'section', 'l6-cumulative')
    assert f"少了 {r['cumulative']['saved']['display']}" in check_site.text_of(cumulative)
    assert len(check_site.descendants(cumulative, 'i', 'l6-bar-range')) == 1


INTERVAL_PATHS = [['turns', 0, 'full'], ['turns', 4, 'trim'], ['plateau'],
                  ['cumulative', 'full'], ['cumulative', 'trim'], ['cumulative', 'saved']]


@pytest.mark.parametrize('path', INTERVAL_PATHS)
@pytest.mark.parametrize('case', ['reversed', 'display_shape', 'display_value'])
def test_every_interval_rejects_bad_endpoints_and_display(path, case):
    data = records()
    parent, key = field_at(data['TURN_input'], path)
    value = parent[key]
    if case == 'reversed':
        value['lo'] = value['hi'] + 1
    elif case == 'display_shape':
        value['display'] = str(value['lo']) if value['lo'] < value['hi'] else f"{value['lo']}–{value['hi']}"
    else:
        value['display'] = str(value['hi'] + 1)
    with pytest.raises(ValueError):
        render('TURN_input', data)


def test_turnbars_preserves_display_typography_and_optional_sections():
    data = records()
    r = data['TURN_input']
    r['turns'][4]['trim']['display'] = ' 75 到 77 '
    assert '> 75 到 77 </span>' in render('TURN_input', data)
    r['plateau'] = r['cumulative'] = None
    p = parsed(render('TURN_input', data))
    assert not check_site.descendants(p.root, 'i', 'l6-plateau-band')
    assert not check_site.descendants(p.root, 'section', 'l6-cumulative')
    assert 'width:100.000000%' in render('TURN_input', data)


def test_zero_values_have_zero_length_without_division_by_zero():
    data = records()
    r = data['TURN_input']
    r['plateau'] = r['cumulative'] = None
    for turn in r['turns']:
        for key in ('full', 'trim'):
            turn[key] = dict(lo=0, hi=0, display='0')
    p = parsed(render('TURN_input', data))
    assert all(percentages(x.attrs['style'])['width'] == 0
               for x in check_site.descendants(p.root, 'i', 'l6-bar-solid'))


def test_classgrid_symbols_accessible_labels_models_and_tallies():
    r = records()['GRID_classes']
    p = parsed(render('GRID_classes'))
    rows = check_site.descendants(p.root, 'div', 'l6-grid-row')
    assert len(rows) == len(r['rows'])
    for record, row in zip(r['rows'], rows):
        cells = check_site.descendants(row, 'span', 'l6-grid-cell')
        assert len(cells) == record['tally']['total']
        assert record['model'] in check_site.text_of(row)
        for number, (cell, expected) in enumerate(zip(cells, record['cells']), 1):
            cls = expected['class']
            assert f'l6-grid-{cls}' in cell.attrs['class'].split()
            assert cell.attrs['role'] == 'img' and f'第 {number} 遍' in cell.attrs['aria-label']
            assert next(x['text'] for x in r['legend'] if x['class'] == cls) in cell.attrs['aria-label']
            assert check_site.text_of(cell) == ('✓' if cls in ('correct', 'named') else '·')
            assert not {'bad', 'red', 'error'} & set(cell.attrs['class'].split())
        tally = record['tally']
        assert f"{tally['short']} {tally['n']} / {tally['total']}" in check_site.text_of(row)


@pytest.mark.parametrize('case', ['cells', 'total', 'tally', 'unknown_class', 'undeclared_class', 'human_labeler'])
def test_classgrid_invalid_counts_classes_and_labeler_fail(case):
    data = records()
    r = data['GRID_classes']
    row = r['rows'][0]
    if case == 'cells':
        row['cells'].pop()
    elif case == 'total':
        row['tally']['total'] -= 1
    elif case == 'tally':
        row['tally']['n'] -= 1
    elif case == 'unknown_class':
        row['cells'][0]['class'] = '<b>x</b>'
    elif case == 'undeclared_class':
        r['legend'] = r['legend'][1:]
    else:
        r['labeler'] = '真人标注'
    with pytest.raises(ValueError):
        render('GRID_classes', data)


@pytest.mark.parametrize('rid', ['WIN_shice', 'TURN_input', 'GRID_classes'])
def test_measured_figures_must_not_say_sketch(rid):
    data = records()
    data[rid]['note'] = '示意'
    with pytest.raises(ValueError):
        render(rid, data)


@pytest.mark.parametrize('rid,path', [
    ('WIN_shice', ['caliber']), ('TURN_input', ['model']), ('TURN_input', ['runs']),
    ('TURN_input', ['turns', 0, 'full', 'lo']), ('TURN_input', ['turns', 0, 'trim', 'hi']),
    ('GRID_classes', ['rows', 0, 'model']), ('GRID_classes', ['rows', 0, 'tally', 'n']),
])
def test_required_read_values_cannot_be_empty(rid, path):
    data = records()
    parent, key = field_at(data[rid], path)
    parent[key] = None
    with pytest.raises(AssertionError, match='不能为空'):
        render(rid, data)


@pytest.mark.parametrize('rid', ['WIN_shice', 'TURN_input', 'GRID_classes'])
def test_measured_date_required(rid):
    data = records()
    data[rid]['date'] = None
    with pytest.raises(AssertionError, match='不能为空'):
        render(rid, data)


def site_check(data, output):
    checker = object.__new__(check_site.SiteChecker)
    checker.records, checker.checks = data, []
    checker.source_pages = lambda: [('unit', 'book', 'page', {}, None)]
    checker.parser_for = lambda page: parsed(output)
    checker.check_ch_shice()
    assert len(checker.checks) == 1
    return checker.checks[0]


def site_figures(data):
    # The existing whole-chapter rule requires at least six figures.
    return ''.join(render(rid, data) for rid in data) * 2


def test_whole_site_checker_accepts_new_honesty_tags():
    data = records()
    result = site_check(data, site_figures(data))
    assert result['ok'], result['detail']


@pytest.mark.parametrize('case', ['sketch_measured_stamp', 'measured_sketch_text', 'measured_sketch_stamp',
                                 'missing_measured', 'human_labeler', 'wrong_honest', 'sketch_caption'])
def test_whole_site_checker_rejects_honesty_violations(case):
    data = records()
    output = site_figures(data)
    if case == 'sketch_measured_stamp':
        output = output.replace('class="tag tag-shiyi"', 'class="tag tag-shiyi tag-shice"')
    elif case == 'measured_sketch_text':
        output = output.replace(data['TURN_input']['note'], '示意')
    elif case == 'measured_sketch_stamp':
        output = output.replace('class="tag tag-shice"', 'class="tag tag-shice tag-shiyi"')
    elif case == 'missing_measured':
        data['WIN_shice']['notes'][1]['state'] = 'missing'
    elif case == 'human_labeler':
        data['GRID_classes']['labeler'] = '真人标注'
    elif case == 'wrong_honest':
        data['TURN_input']['honest'] = 'shiyi'
    else:
        output = output.replace('示意', '位置')
    assert not site_check(data, output)['ok']


def test_new_chapter_drawer_counts_sketches_and_keeps_ids():
    data = records()
    output = chapter(data)
    p = parsed(output)
    evidence = next(x for x in check_site.descendants(p.root, 'details') if x.attrs.get('id') == 'evidence')
    text = check_site.text_of(evidence)
    assert '共 4 条：实测 3 条、示意 1 条、官方引文 0 条' in text
    assert '数是我们自编的' not in text
    assert all(rid in text for rid in data)
    measured = {k: v for k, v in data.items() if v['honest'] == 'shice'}
    assert '共 3 条：实测 3 条、示意 0 条、官方引文 0 条' in chapter(measured)


def test_l6_css_uses_theme_variables_and_neutral_gray_without_changing_old_rules():
    css = (ROOT / 'docs/whiteboard/ebook/book.css').read_text(encoding='utf-8')
    new = css[css.index('/* 第 6 课：'):]
    assert '.l6-window-layout { grid-template-columns: minmax(0, 1fr); }' in new
    assert 'repeat(10, minmax(0, 1fr))' in new and 'overflow-wrap: anywhere' in new
    gray = re.search(r'\.l6-grid-unknown, \.l6-grid-not_named \{([^}]+)\}', new).group(1)
    assert 'var(--muted)' in gray and 'var(--note-bg)' in gray
    assert '--red' not in gray and '--bad' not in gray
    torn = re.search(r'\.l6-window-torn \{([^}]+)\}', new).group(1)
    assert '--muted' in torn and '--red' not in torn and '--bad' not in torn
    assert not re.search(r'#[0-9a-fA-F]{3,8}\b', new)


def test_examples_match_lesson_sources_and_do_not_relabel_the_observations():
    r = records()
    t = json.loads((ROOT / 'projects/agent-long-chat-cn/review/scene/real_tables.json').read_text(encoding='utf-8'))
    chart = r['TURN_input']
    source = t['e2']['m1']
    assert chart['model'] == source['model'] == t['models']['m1']
    assert chart['date'] == t['date'] and chart['runs'] == source['runs']
    for row, full, trim in zip(chart['turns'], source['turns']['FULL'], source['turns']['TRIM6']):
        assert row['turn'] == full['turn'] == trim['turn']
        for key, item in [('full', full), ('trim', trim)]:
            assert [row[key]['lo'], row[key]['hi']] == item['span']
            assert row[key]['display'] == item['display']
    assert [chart['plateau']['lo'], chart['plateau']['hi']] == source['turn4_to_8_span']
    for key, mode in [('full', 'FULL'), ('trim', 'TRIM6')]:
        assert [chart['cumulative'][key]['lo'], chart['cumulative'][key]['hi']] == source['cumulative_range'][mode]['cum_input']
    assert [chart['cumulative']['saved']['lo'], chart['cumulative']['saved']['hi']] == source['saved_range']
    assert [{k: n[k] for k in ('role', 'role_cn', 'text')} for n in r['WIN_shice']['notes']] == t['stacks']['E1_FULL']
    grid = r['GRID_classes']
    for row, (group, key) in zip(grid['rows'], [('e1', 'FULL/m1'), ('e1', 'TRIM_EARLY/m1'),
                                               ('e1b', 'KEEP_SYSTEM/m1'), ('e1b', 'DROP_SYSTEM/m1')]):
        assert row['cells'] == [{'class': c['class']} for c in t[group][key]['cells']]
    assert 'AI 模型' in grid['labeler'] and '真人标注' not in grid['labeler']


def test_examples_are_reproducible_from_lesson_data_without_literal_measurements():
    t = json.loads((ROOT / 'projects/agent-long-chat-cn/review/scene/real_tables.json').read_text(encoding='utf-8'))
    assert examples_from_tables(t) == records()
    t['e2']['m1']['runs'] = None
    with pytest.raises(AssertionError, match='不能为空'):
        examples_from_tables(t)
