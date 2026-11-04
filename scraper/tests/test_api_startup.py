"""Startup diagnostics must not claim a server is listening before binding."""
import errno
from unittest.mock import MagicMock, Mock

import local_search_api as api


def test_occupied_port_is_actionable_without_false_readiness(monkeypatch, capsys):
    monkeypatch.setattr(api, 'load_database_config', lambda: None)
    monkeypatch.setattr(api, 'ThreadingHTTPServer', Mock(side_effect=OSError(errno.EADDRINUSE, 'Address already in use')))
    assert api.main() == 1
    output = capsys.readouterr()
    assert 'already in use' in output.err
    assert 'Ctrl+C' in output.err
    assert 'listening' not in output.out


def test_configuration_failure_never_opens_socket(monkeypatch, capsys):
    monkeypatch.setattr(api, 'load_database_config', Mock(side_effect=api.ConfigurationError('Missing configuration')))
    server = Mock()
    monkeypatch.setattr(api, 'ThreadingHTTPServer', server)
    assert api.main() == 1
    server.assert_not_called()
    assert 'Missing configuration' in capsys.readouterr().err


def test_success_and_keyboard_interrupt_close_server_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(api, 'load_database_config', lambda: None)
    server = MagicMock()
    server.serve_forever.side_effect = KeyboardInterrupt
    monkeypatch.setattr(api, 'ThreadingHTTPServer', Mock(return_value=server))
    assert api.main() == 0
    server.serve_forever.assert_called_once()
    server.__exit__.assert_called_once()
    output = capsys.readouterr()
    assert 'listening at' in output.out
    assert 'stopped' in output.out
    assert not output.err
