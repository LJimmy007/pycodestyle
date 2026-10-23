import io
import os.path
import subprocess
import sys
import tokenize

import pytest

from pycodestyle import Checker
from pycodestyle import expand_indent
from pycodestyle import get_parser
from pycodestyle import mute_string
from pycodestyle import read_config
from pycodestyle import StyleGuide


@pytest.mark.parametrize(
    ('s', 'expected'),
    (
        ('    ', 4),
        ('\t', 8),
        ('       \t', 8),
        ('        \t', 16),
    ),
)
def test_expand_indent(s, expected):
    assert expand_indent(s) == expected


@pytest.mark.parametrize(
    ('s', 'expected'),
    (
        ('"abc"', '"xxx"'),
        ("'''abc'''", "'''xxx'''"),
        ("r'abc'", "r'xxx'"),
    ),
)
def test_mute_string(s, expected):
    assert mute_string(s) == expected


def test_fstring_logical_line():
    src = '''\
f'hello {{ {thing} }} world'
'''
    checker = Checker(lines=src.splitlines())
    checker.tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    checker.build_tokens_line()

    if sys.version_info >= (3, 12):  # pragma: >=3.12 cover
        assert checker.logical_line == "f'xxxxxxxxx{thing}xxxxxxxxx'"
    else:  # pragma: <3.12 cover
        assert checker.logical_line == "f'xxxxxxxxxxxxxxxxxxxxxxxxx'"


def test_read_config_prefix(tmp_path):
    tmp_path.joinpath('setup.cfg').write_text('[pycodestyle]\nexclude = root')

    adir = tmp_path.joinpath('aaa')
    adir.mkdir()
    adir.joinpath('setup.cfg').write_text('[pycodestyle]\nexclude = aaa')

    bdir = tmp_path.joinpath('aaabbb')
    bdir.mkdir()
    b_t = bdir.joinpath('t.py')
    b_t.touch()
    bdir.joinpath('setup.cfg').write_text('[pycodestyle]\nexclude = bbb')

    cdir = tmp_path.joinpath('aaaccc')
    cdir.mkdir()
    c_t = cdir.joinpath('t.py')
    c_t.touch()
    cdir.joinpath('setup.cfg').write_text('[pycodestyle]\nexclude = ccc')

    arglist = [str(b_t), str(c_t)]
    parser = get_parser()
    parser.add_option('--config')
    opts, args = parser.parse_args(arglist)

    # `aaa/setup.cfg` should not be read -- it is not passed on cmdline
    opts = read_config(opts, args, arglist, parser)
    assert opts.exclude == ['root']


@pytest.mark.parametrize('dirname', ('.', './', 'relative', 'absolute'))
@pytest.mark.parametrize(
    ('exclude', 'expected'),
    ((['.*'], 2), (['.*', 'subdir'], 1), ([], 4)),
)
def test_input_dir_exclude_hidden(
        tmp_path, monkeypatch, dirname, exclude, expected,
):
    tmp_path.joinpath('bad.py').write_text('x=1\n')
    tmp_path.joinpath('.hidden.py').write_text('x=1\n')
    for subdir in ('subdir', '.hidden'):
        tmp_path.joinpath(subdir).mkdir()
        tmp_path.joinpath(subdir, 'bad.py').write_text('x=1\n')
    monkeypatch.chdir(tmp_path)
    if dirname == 'absolute':
        dirname = str(tmp_path)
    elif dirname == 'relative':
        monkeypatch.chdir(tmp_path.parent)
        dirname = tmp_path.name

    style = StyleGuide(select=['E225'], exclude=exclude, quiet=True)
    report = style.check_files([dirname])
    assert report.total_errors == expected
    assert report.counters['files'] == expected


@pytest.mark.parametrize('dirname', ('.', './', 'relative', 'absolute'))
@pytest.mark.parametrize('exclude', ('basename', 'absolute', '*'))
def test_input_dir_excluded_root(tmp_path, monkeypatch, dirname, exclude):
    tmp_path.joinpath('bad.py').write_text('x=1\n')
    monkeypatch.chdir(tmp_path)
    if dirname == 'absolute':
        dirname = str(tmp_path)
    elif dirname == 'relative':
        monkeypatch.chdir(tmp_path.parent)
        dirname = tmp_path.name
    if exclude == 'basename':
        exclude = tmp_path.name
    elif exclude == 'absolute':
        exclude = str(tmp_path)

    style = StyleGuide(select=['E225'], exclude=[exclude], quiet=True)
    report = style.check_files([dirname])
    assert report.total_errors == 0
    assert report.counters['files'] == 0


def test_input_dir_hidden_root(tmp_path, monkeypatch):
    hidden = tmp_path.joinpath('.hidden')
    hidden.mkdir()
    hidden.joinpath('bad.py').write_text('x=1\n')
    monkeypatch.chdir(hidden)

    style = StyleGuide(select=['E225'], exclude=['.*'], quiet=True)
    report = style.check_files(['.'])
    assert report.total_errors == 0
    assert report.counters['files'] == 0


def test_cli_exclude_hidden_dot(tmp_path):
    tmp_path.joinpath('bad.py').write_text('x=1\n')
    tmp_path.joinpath('.hidden.py').write_text('x=1\n')
    tmp_path.joinpath('.hidden').mkdir()
    tmp_path.joinpath('.hidden', 'bad.py').write_text('x=1\n')
    script = os.path.join(os.path.dirname(__file__), '..', 'pycodestyle.py')
    result = subprocess.run(
        (sys.executable, script, '--select=E225', '--exclude=.*', '.'),
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert result.stderr == ''
    assert result.stdout == (
        f'{os.path.join(".", "bad.py")}:1:2: '
        'E225 missing whitespace around operator\n'
    )
