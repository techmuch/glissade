import socket

from glissade.cli import build_parser, find_available_port, main


def test_cli_init_and_decks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    # 1. Run glissade init
    ret = main(["init"])
    assert ret == 0
    assert (tmp_path / "decks").is_dir()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "glissade.schema.json").is_file()

    # 2. Run glissade decks
    ret = main(["decks"])
    assert ret == 0

    # 3. Run glissade themes
    ret = main(["themes"])
    assert ret == 0

def test_cli_schema_and_update(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init"])

    # Refresh schema
    ret = main(["schema"])
    assert ret == 0

    # Update project owned files
    ret = main(["update"])
    assert ret == 0

def test_cli_no_command():
    ret = main([])
    assert ret == 0

def test_cli_check_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init"])

    # Run glissade check on scaffolded project
    ret = main(["check"])
    assert ret == 0


def test_cli_start_watch_defaults():
    parser = build_parser()

    args = parser.parse_args(["start"])
    assert args.no_watch is False

    args = parser.parse_args(["start", "--no-watch"])
    assert args.no_watch is True

    args = parser.parse_args(["demo"])
    assert args.no_watch is False


def test_find_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    # Free port returns immediately
    assert find_available_port("127.0.0.1", free_port) == free_port

    # Occupied port increments to the next available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
        s1.bind(("127.0.0.1", 0))
        s1.listen(1)
        busy_port = s1.getsockname()[1]

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
            s2.bind(("127.0.0.1", busy_port + 1))
            s2.listen(1)

            next_free = find_available_port("127.0.0.1", busy_port)
            assert next_free >= busy_port + 2

