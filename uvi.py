#!/usr/bin/env -S uv run --script
"""uvi.py -- based interactive uv init script"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "rich>=13.9.4",
# ]
# ///

import os
import pty
import re
import subprocess
import sys

from rich import print as rprint

__version__ = "1.0.0"

# ************************** CONSTS **************************

PROJ_TYPES = {
    "b": "bare",
    "p": "package",
    "a": "app",
    "l": "lib",
    "s": "script",
}

PY3_SUPPORT = range(7, 15)
PROJ_TYPES_STR = f"{', '.join(f'[cyan]{k}/{v}[/cyan]' for k, v in PROJ_TYPES.items())}"
NF_ARR = "󱞩"

USAGE = "[bold green]Usage:[/] [cyan]uvi.py [dim][-h][/] type name[/]"
HELP = f"""{__doc__}

{USAGE}

[bold green]Positionals:[/]
  [cyan]type[/]           Project type [dim cyan][{PROJ_TYPES_STR}][/]
  [cyan]name[/]           Project name

[bold green]Optionals:[/bold green]
  [cyan]-h[/], [cyan]--help[/]     Show this help message and exit
  [cyan]-v[/], [cyan]--version[/]   Show program's version number and exit
"""


# *************************** I/O ****************************


def perr(msg: str) -> None:
    """Print error message to stderr"""
    rprint(f"[red]error:[/] {msg}", file=sys.stderr)


def inp(prompt: str, sup: str | None = None) -> str:
    """Get user input with optional supplementary text"""
    sup_str = f" [cyan]({sup})" if sup is not None else ""
    return input(f"[green]{prompt}{sup_str}[/] > ").strip()


def yn_inp(prompt: str) -> bool:
    """Get boolean input (yes or no)"""
    err_str = ""
    while True:
        inpt = inp(f"{err_str}{prompt}", "y/n").lower()
        if inpt in {"yes", "y"}:
            return True
        elif inpt in {"no", "n"}:
            return False
        err_str = "[red]! [/]"


def detect_missing_ver(output: str) -> str | None:
    """Detect if error is 'no interpreter found' with managed download available"""
    pattern = r"No interpreter found for Python (\d+\.\d+).*A managed Python download is available.*use `uv python install \1`"
    match = re.search(pattern, output, re.DOTALL)
    return match.group(1) if match else None


def install_missing_ver(missing_ver: str) -> None:
    """Install missing Python version"""
    if yn_inp(f"install Python {missing_ver}?"):
        rprint(f"\n[cyan]installing Python {missing_ver}[/]", file=sys.stderr)
        install_code, _ = cmd_run(f"uv python install {missing_ver}")
        if install_code != 0:
            perr(f"failed to install Python {missing_ver}")
            sys.exit(install_code)
        rprint("[cyan]retrying init[/]\n", file=sys.stderr)


def cmd_run(cmd: str) -> tuple[int, str]:
    """Run command, stream output to stdout, return exit code and captured output"""
    master, slave = pty.openpty()
    outbuf = []

    with subprocess.Popen(
        cmd, stdout=slave, stderr=slave, shell=True, text=True, close_fds=True
    ) as proc:
        os.close(slave)
        try:
            while True:
                data = os.read(master, 1024)
                if not data:
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
                outbuf.append(data.decode("utf-8", errors="replace"))
        except OSError:
            pass

        exit_code = proc.wait()

    return exit_code, "".join(outbuf)


# ********************* ARG VALIDATION ***********************


def valid_proj_type(proj_type: str) -> bool:
    if proj_type not in PROJ_TYPES and proj_type not in PROJ_TYPES.values():
        perr(f"invalid project type: [yellow]{proj_type}[/] (see [cyan]uvi --help[/])")
        return False
    return True


def valid_proj_name(proj_name: str) -> bool:
    if not proj_name.isidentifier():
        perr(f"invalid project name: {proj_name}")
        return False
    return True


def parse_args() -> tuple[str, str]:
    """Validate CLI args"""
    argc = len(sys.argv) - 1
    if "-h" in sys.argv or "--help" in sys.argv:
        rprint(HELP)
        sys.exit(0)

    if "-v" in sys.argv or "--version" in sys.argv:
        rprint(f"[cyan]uvi.py[/] [green]v{__version__}[/]")
        sys.exit(0)

    if argc == 0:
        perr("missing args: project type & project name")
        sys.exit(2)

    if argc == 1:
        if valid_proj_type(sys.argv[1]):
            perr("missing arg: project name")
        sys.exit(2)

    elif argc == 2:
        if not valid_proj_type(sys.argv[1]) or not valid_proj_name(sys.argv[2]):
            sys.exit(2)

    elif argc > 2:
        perr("too many args: give only project type & project name")
        sys.exit(2)

    proj_type_arg = sys.argv[1]
    proj_type = PROJ_TYPES.get(proj_type_arg, proj_type_arg)
    return proj_type, sys.argv[2]


# ********************** MAIN INPUTS *************************


def get_ver() -> str:
    while True:
        ver = inp("version", "enter for default").lower()
        if ver == "":
            return f"3.{PY3_SUPPORT[-2]}"

        if ver in (f"3.{i}" for i in PY3_SUPPORT):
            return ver

        perr(
            f"invalid version: [yellow]{ver}[/] "
            f"([cyan]3.{PY3_SUPPORT[0]}[/]-[cyan]3.{PY3_SUPPORT[-1]}[/] only)"
        )


def get_desc() -> str:
    return repr(inp("desc"))


def get_vcs() -> bool:
    return yn_inp("vcs")


def get_rm() -> bool:
    return yn_inp("readme")


# ************************* MAIN *****************************


def main() -> None:
    try:
        pt, pn = parse_args()
        is_script = pt == "script"
        ver = get_ver()

        if is_script:
            cmd = f"uv init {pn} --{pt} --python {ver}"
        else:
            desc = get_desc()
            vcs = "'git'" if get_vcs() else "'none'"
            readme_flag = "" if get_rm() else "--no-readme"
            cmd = f"uv init {pn} --{pt} --python {ver} --description {desc} --vcs {vcs} {readme_flag}"

        exit_code, output = cmd_run(cmd)

        if exit_code != 0:
            missing_ver = detect_missing_ver(output)
            if missing_ver:
                install_missing_ver(missing_ver)
                exit_code, _ = cmd_run(cmd)

        sys.exit(exit_code)

    except KeyboardInterrupt:
        rprint("\n[red]stopped[/]")
        sys.exit(130)


if __name__ == "__main__":
    main()
