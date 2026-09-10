from transcribe_inbox.cli import build_parser

def test_retry_subcommand_parses_job_id():
    parser = build_parser()
    args = parser.parse_args(["retry", "abc-123"])
    assert args.command == "retry"
    assert args.job_id == "abc-123"
