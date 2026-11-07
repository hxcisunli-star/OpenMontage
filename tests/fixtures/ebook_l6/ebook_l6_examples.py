"""Build frozen-schema lesson 6 examples from the archived lesson tables."""
from copy import deepcopy


def examples_from_tables(t):
    def required(obj, key):
        value = obj[key]
        assert value is not None and value != '' and value != [], f'{key} 不能为空'
        return value

    def interval(span, display):
        assert span and len(span) == 2 and display, '范围和显示文字不能为空'
        assert all(value is not None for value in span), '范围端点不能为空'
        return dict(lo=span[0], hi=span[1], display=display)

    def span_display(span):
        assert span and all(x is not None for x in span), '范围端点不能为空'
        return str(span[0]) if span[0] == span[1] else f'{span[0]}–{span[1]}'

    date = required(t, 'date')
    models = required(t, 'models')
    model = required(models, 'm1')
    scope = required(t, 'scope')
    caliber = (f'只代表我们用的{required(scope, "relay")}，{date}，两个标称模型'
               f'（{model}、{required(models, "m2")}，背后是谁无法核实），'
               f'关了思考，{required(scope, "history")}；只限这一天、这两个模型和这一句固定问法。')
    stacks = required(t, 'stacks')
    original = required(stacks, 'E1_FULL')
    trimmed = required(stacks, 'E1_TRIM_EARLY')
    notes = [dict(x, state='pinned' if x['role'] == 'system' else
                  'kept' if x in trimmed else 'torn', mark=None) for x in original]
    next(x for x in notes if x['state'] == 'kept' and x['role'] == 'user')['mark'] = '窗口里最早的用户消息'
    window = dict(kind='window', title='这次发出的纸条', date=date, honest='shice', caliber=caliber,
                  notes=notes, folder=dict(label='程序手里', count=sum(x['state'] == 'torn' for x in notes)),
                  note='取件码是造的号码，不是个人信息。截断就是从这次发出的纸条摞里去掉一段。')
    sketch = deepcopy(window)
    sketch.update(title='缺了一张纸条的示意', honest='shiyi', date=None,
                  caliber='只画纸条的位置，缺的纸条是占位。', note='示意图：缺的纸条只是占位。')
    next(x for x in sketch['notes'] if x['state'] == 'torn')['state'] = 'missing'
    sketch['folder']['count'] = sum(x['state'] == 'torn' for x in sketch['notes'])

    e2 = required(required(t, 'e2'), 'm1')
    turns = required(e2, 'turns')
    full, trim = required(turns, 'FULL'), required(turns, 'TRIM6')
    assert len(full) == len(trim), '两组轮数应相同'
    turn_data = [dict(turn=required(f, 'turn'),
                      full=interval(required(f, 'span'), required(f, 'display')),
                      trim=interval(required(s, 'span'), required(s, 'display')))
                 for f, s in zip(full, trim)]
    ranges, displays = required(e2, 'cumulative_range'), required(e2, 'cumulative_display')
    cumulative = {key: interval(required(required(ranges, source), 'cum_input'),
                                required(required(displays, source), 'cum_input'))
                  for key, source in [('full', 'FULL'), ('trim', 'TRIM6')]}
    saved = required(e2, 'saved_range')
    cumulative['saved'] = interval(saved, span_display(saved))
    plateau = required(e2, 'turn4_to_8_span')
    first = required(required(t, 'window'), 'first_turn_starting_with_assistant')
    turnbars = dict(kind='turnbars', title='每轮发了多少词元', date=date, honest='shice',
                    caliber=caliber, model=required(e2, 'model'), turns=turn_data,
                    plateau=dict(from_turn=first, **interval(plateau, span_display(plateau))),
                    cumulative=cumulative, runs=required(e2, 'runs'),
                    note='词元是模型处理文字的小块。累计就是把各轮的数加起来。条长由请求里装了什么决定。')
    legend = [dict(**{'class': cls}, text=text) for cls, text in
              [('correct', '答对取件码'), ('unknown', '说没有看到取件码'),
               ('named', '说出名字'), ('not_named', '没有说出名字')]]
    rows = []
    for group, key, cls, label in [('e1', 'FULL/m1', 'correct', '取件码：整摞'),
                                   ('e1', 'TRIM_EARLY/m1', 'unknown', '取件码：切掉早先的纸条'),
                                   ('e1b', 'KEEP_SYSTEM/m1', 'named', '名字：保留系统消息'),
                                   ('e1b', 'DROP_SYSTEM/m1', 'not_named', '名字：去掉系统消息')]:
        row = required(required(t, group), key)
        cells = [{'class': required(x, 'class')} for x in required(row, 'cells')]
        rows.append(dict(label=label, model=model, cells=cells,
                         tally=dict(**{'class': cls}, n=sum(x['class'] == cls for x in cells),
                                    total=required(row, 'n'), short=next(x['text'] for x in legend if x['class'] == cls))))
    grid = dict(kind='classgrid', title='按类别看各遍回答', date=date, honest='shice', caliber=caliber,
                legend=legend, rows=rows, labeler='AI 模型标注与核对',
                note='取件码是造的号码，不是个人信息。名字这一组，其余的消息里没有任何名字。')
    return dict(WIN_shice=window, WIN_shiyi=sketch, TURN_input=turnbars, GRID_classes=grid)
