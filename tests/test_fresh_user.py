"""Fresh CLI consumers and wrapper lifecycle regressions; synthetic inputs only."""
import json
import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from agent_tally.cli import cli
from agent_tally.budget import BudgetManager
from agent_tally.pricing import PricingConfig
from agent_tally.storage import Storage
from agent_tally.wrapper import AgentWrapper


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr('agent_tally.storage.DEFAULT_DB_PATH', tmp_path / 'db.sqlite')
    monkeypatch.setattr('agent_tally.budget.DEFAULT_BUDGET_FILE', tmp_path / 'budget.yaml')
    monkeypatch.setattr('agent_tally.pricing.DEFAULT_PRICING_FILE', tmp_path / 'pricing.yaml')
    return tmp_path


@pytest.mark.parametrize('command,expected', [
    (['history', '--json'], []), (['recent', '--json'], []),
    (['export', '--format', 'json'], []),
    (['top', '--json'], []),
    (['hourly', '--json'], {'since': '7d', 'hourly': []}),
])
def test_empty_json(isolated, command, expected):
    result = CliRunner().invoke(cli, command)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected


@pytest.mark.parametrize('value', ['-1', 'nan', 'inf'])
def test_invalid_budget_rejected_atomically(isolated, value):
    runner = CliRunner()
    assert runner.invoke(cli, ['budget', 'set', '--daily', '5']).exit_code == 0
    result = runner.invoke(cli, ['budget', 'set', '--daily', '10', '--session', value])
    assert result.exit_code == 2
    assert BudgetManager().config.daily_limit == 5
    assert BudgetManager().config.session_limit is None


def test_unknown_price_is_not_free(isolated):
    result = CliRunner().invoke(cli, ['cost', 'unknown-fixture-model', '100', '50', '--json'])
    data = json.loads(result.output)
    assert data['pricing_status'] == 'unknown'
    assert data['estimated_cost_usd'] is None


def test_welcome_uses_real_command():
    assert 'agent-tally run claude' in CliRunner().invoke(cli, []).output


def test_child_flags_are_forwarded(isolated, monkeypatch):
    wrapper = MagicMock()
    wrapper.run.return_value = 0
    factory = MagicMock(return_value=wrapper)
    monkeypatch.setattr('agent_tally.wrapper.AgentWrapper', factory)
    result = CliRunner().invoke(cli, ['run', '--tag', 'qa', 'fixture-agent', '--help', '--tag', 'child'])
    assert result.exit_code == 0
    factory.assert_called_once_with(['fixture-agent', '--help', '--tag', 'child'])
    assert wrapper.tags == ['qa']


def make_wrapper(tmp_path, **kwargs):
    return AgentWrapper(
        [sys.executable, '-c', 'print("model: fixture-model\\ntokens_in: 1000 tokens_out: 500")'],
        storage=Storage(tmp_path / 'db.sqlite'),
        budget_manager=BudgetManager(tmp_path / 'budget.yaml'),
        pricing=PricingConfig(tmp_path / 'pricing.yaml'), **kwargs)


def test_budget_targets_child_and_saves_usage(tmp_path, monkeypatch):
    wrapper = make_wrapper(tmp_path)
    wrapper.pricing.set('fixture-model', 2, 8)
    wrapper.budget_manager.set_limits(session=0.001)
    kill = MagicMock()
    monkeypatch.setattr(wrapper.budget_manager, 'kill_process', kill)
    popen = __import__('subprocess').Popen
    children = []
    def capture(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr('agent_tally.wrapper.subprocess.Popen', capture)
    assert wrapper.run() == 137
    kill.assert_called_once_with(children[0].pid)
    stored = wrapper.storage.get(wrapper.session.id)
    assert stored.ended_at is not None
    assert stored.cost == pytest.approx(0.006)


def test_interruption_terminates_child_and_saves_partial_usage(tmp_path, monkeypatch):
    wrapper = make_wrapper(tmp_path, enable_ticker=False)
    wrapper.pricing.set('fixture-model', 2, 8)
    child = MagicMock()
    child.poll.return_value = None
    def output():
        yield 'model: fixture-model\n'
        yield 'tokens_in: 1000 tokens_out: 500\n'
        raise KeyboardInterrupt
    child.stdout = output()
    monkeypatch.setattr('agent_tally.wrapper.subprocess.Popen', lambda *a, **k: child)
    assert wrapper.run() == 130
    child.terminate.assert_called_once()
    child.wait.assert_called_once()
    stored = wrapper.storage.get(wrapper.session.id)
    assert stored.ended_at is not None
    assert stored.cost == pytest.approx(0.006)


def test_launch_failure_is_finalized(tmp_path):
    wrapper = make_wrapper(tmp_path, enable_ticker=False)
    wrapper.args = ['missing-fixture-agent-xyz']
    assert wrapper.run() == 127
    assert wrapper.storage.get(wrapper.session.id).ended_at is not None


def test_task_and_tags_persist(tmp_path):
    wrapper = make_wrapper(tmp_path, enable_ticker=False)
    wrapper.tags = ['qa', 'synthetic']
    assert wrapper.run() == 0
    stored = wrapper.storage.get(wrapper.session.id)
    assert stored.task_prompt
    assert stored.tags == 'qa,synthetic'


def test_daily_budget_includes_current_session(tmp_path):
    from agent_tally.ticker import CostTicker
    manager = BudgetManager(tmp_path / 'budget.yaml')
    manager.set_limits(daily=1)
    ticker = CostTicker('fixture', 'fixture', manager, lambda: 0.8)
    assert ticker.update(0.3).daily_exceeded


def test_ticker_does_not_claim_zero_before_detection(capsys):
    from agent_tally.ticker import CostTicker
    ticker = CostTicker('fixture', 'fixture')
    ticker.start()
    assert 'N/A (usage/pricing unknown)' in capsys.readouterr().out
    ticker.update(0)
    assert '$0.0000' in capsys.readouterr().out


def test_wrapped_run_on_legacy_windows_encoding(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path), PYTHONIOENCODING='cp1252')
    result = subprocess.run([sys.executable, '-c', 'from agent_tally.cli import cli; cli()',
                             'run', sys.executable, '-c', 'print(123)'],
                            env=env, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert b'123' in result.stdout
