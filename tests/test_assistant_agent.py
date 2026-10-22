import json

import pytest

import assistant
import crm

USER = {'id': 1, 'username': 'oilpress', 'role': 'admin'}


@pytest.fixture
def agent(monkeypatch):
    """Агент без базы и без сети: промпт — заглушка, модель отвечает по сценарию."""
    monkeypatch.setattr(assistant, 'build_system_prompt', lambda context=None: 'system')
    saved = []

    def save(user, tool, args, summary):
        action = {'id': f'act{len(saved) + 1}', 'tool': tool, 'summary': summary, 'status': 'pending',
                  'title': assistant.TOOLS[tool]['title']}
        saved.append({'user': user['username'], 'tool': tool, 'args': args})
        return action

    monkeypatch.setattr(assistant, 'save_pending_action', save)

    def run(script, question='вопрос'):
        replies = iter(script)
        sent = []

        def fake_llm(messages):
            sent.append(list(messages))  # снимок: агент дописывает в тот же список
            return next(replies)

        monkeypatch.setattr(assistant, 'call_llm', fake_llm)
        result = assistant.run_agent([{'role': 'user', 'content': question}], USER)
        return result, sent

    run.saved = saved
    return run


def test_parse_decision_tolerates_fences_and_text():
    assert assistant.parse_decision('```json\n{"tool": "stock", "args": {}}\n```') == {'tool': 'stock', 'args': {}}
    assert assistant.parse_decision('Думаю… {"reply": "Готово"} спасибо') == {'reply': 'Готово'}
    assert assistant.parse_decision('<think>{"tool": "x"}</think>{"reply": "ok"}') == {'reply': 'ok'}
    assert assistant.parse_decision('{"foo": 1} {"tool": "sql", "args": {"query": "SELECT 1"}}')['tool'] == 'sql'
    assert assistant.parse_decision('просто текст') is None


def test_read_tool_result_goes_back_to_model(agent, monkeypatch):
    monkeypatch.setitem(assistant.TOOLS['stock'], 'run', lambda args: {'stock': [{'oil_name': 'льняное', 'free_ml': 1500}]})
    result, sent = agent(['{"tool": "stock", "args": {}}', '{"reply": "Льняного свободно 1,5 л"}'])

    assert result['reply'] == 'Льняного свободно 1,5 л'
    assert [step['tool'] for step in result['trace']] == ['stock']
    observation = sent[1][-1]['content']
    assert observation.startswith('РЕЗУЛЬТАТ ИНСТРУМЕНТА stock')
    assert '1500' in observation


def test_sql_tool_rows_are_returned_as_table(agent, monkeypatch):
    monkeypatch.setattr(assistant, 'run_readonly_query',
                        lambda query, max_rows=50: {'columns': ['n'], 'rows': [[7]], 'truncated': False})
    result, _ = agent(['{"tool": "sql", "args": {"query": "SELECT COUNT(*) n FROM orders"}}', '{"reply": "7"}'])
    assert result['tables'] == [{'query': 'SELECT COUNT(*) n FROM orders', 'columns': ['n'], 'rows': [[7]],
                                 'truncated': False}]


def test_write_tool_creates_draft_instead_of_writing(agent, monkeypatch):
    monkeypatch.setitem(assistant.TOOLS['create_task'], 'prepare',
                        lambda args: ({'title': args['title'], 'due_date': None}, f"Задача «{args['title']}»"))
    executed = []
    monkeypatch.setitem(assistant.TOOLS['create_task'], 'execute', lambda args, user: executed.append(args))

    call = '{"tool": "create_task", "args": {"title": "Позвонить Анне"}}'
    result, sent = agent([call, call, '{"reply": "Подготовил задачу"}'])

    assert executed == []  # ничего не записано до подтверждения
    assert len(result['actions']) == 1  # повтор того же черновика не плодит второй
    assert result['actions'][0]['summary'] == 'Задача «Позвонить Анне»'
    assert '_signature' not in result['actions'][0]
    assert 'черновик уже создан' in sent[2][-1]['content']


def test_tool_errors_are_shown_to_model(agent, monkeypatch):
    def failing(args):
        raise crm.CrmError('Товара «оливковое» нет в прайс-листе')

    monkeypatch.setitem(assistant.TOOLS['create_order'], 'prepare', failing)
    result, sent = agent([
        '{"tool": "create_order", "args": {"items": [{"oil_name": "оливковое"}]}}',
        '{"tool": "teleport", "args": {}}',
        '{"reply": "Оливкового нет в прайсе"}',
    ])
    assert 'оливковое' in sent[1][-1]['content']
    assert 'Нет инструмента «teleport»' in sent[2][-1]['content']
    assert result['actions'] == []
    assert [step['ok'] for step in result['trace']] == [False, False]


def test_steps_exhausted_forces_final_answer(agent, monkeypatch):
    monkeypatch.setitem(assistant.TOOLS['stock'], 'run', lambda args: {'stock': []})
    script = ['{"tool": "stock", "args": {}}'] * assistant.MAX_STEPS + ['{"reply": "Итог по данным"}']
    result, sent = agent(script)
    assert result['reply'] == 'Итог по данным'
    assert 'Шаги закончились' in sent[-1][-1]['content']


def test_history_must_end_with_user_message():
    with pytest.raises(crm.CrmError):
        assistant._history([{'role': 'assistant', 'content': 'привет'}])


def test_parse_order_text_resolves_items_and_customer(monkeypatch):
    llm_reply = json.dumps({
        'customer': {'name': 'Анна', 'phone': '+7 905 777-66-55'},
        'items': [{'oil_name': 'льняное', 'volume': 500, 'count': 2},
                  {'oil_name': 'оливковое', 'volume': 500, 'count': 1}],
        'shipping_date': '2026-10-24',
        'note': 'после 18',
    }, ensure_ascii=False)
    monkeypatch.setattr(assistant, 'call_llm', lambda messages: llm_reply)
    monkeypatch.setattr(assistant, '_price_rows', lambda: [{'oil_name': 'льняное', 'volume': 500, 'price': 870.0}])

    def resolve(items):
        if items[0]['oil_name'] == 'оливковое':
            raise crm.CrmError('Товара «оливковое» нет в прайс-листе')
        return [{**items[0], 'price': 870.0, 'seed_weight_kg': 0, 'seed_price_per_kg': 0}]

    monkeypatch.setattr(crm, 'resolve_order_items', resolve)
    monkeypatch.setattr(crm, 'find_customer_by_phone', lambda phone: {'id': 5, 'name': 'Анна'})
    monkeypatch.setattr(crm, 'get_customer_row', lambda customer_id: {
        'id': 5, 'full_name': 'Анна Смирнова', 'phone': '89057776655', 'orders_count': 3, 'last_order_date': None})

    draft = assistant.parse_order_text('Анна +7 905 777-66-55 две по пол-литра льняного и оливковое')
    assert draft['customer_match']['id'] == 5
    assert draft['items'][0]['oil_name'] == 'льняное' and draft['items'][0]['count'] == 2
    assert draft['shipping_date'] == '2026-10-24'
    assert draft['note'] == 'после 18'
    assert draft['warnings'] == ['Товара «оливковое» нет в прайс-листе']
