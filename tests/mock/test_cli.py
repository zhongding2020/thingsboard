from unittest.mock import patch

from click.testing import CliRunner

from process_opt.mock.cli import main


def test_cli_help_succeeds() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "seed" in result.output
    assert "stream" in result.output


def test_seed_help_succeeds() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["seed", "--help"])
    assert result.exit_code == 0


def test_stream_help_succeeds() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["stream", "--help"])
    assert result.exit_code == 0


@patch("process_opt.mock.cli.send_batch", return_value=(3, 0))
def test_seed_sends_messages(mock_send_batch: object) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["seed", "--count", "3"])
    assert result.exit_code == 0
    assert "3 sent" in result.output


@patch("process_opt.mock.cli.send_batch", return_value=(1, 0))
def test_seed_custom_device_type(mock_send_batch: object) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["seed", "--count", "1", "--device-type", "injection-molder"])
    assert result.exit_code == 0
